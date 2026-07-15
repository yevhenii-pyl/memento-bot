import uuid

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.notifications import service as notif_service
from bot.shared.exceptions import (
    DeadlineInPastError,
    DeadlineParseError,
    DeadlineTooSoonError,
    OutcomeAlreadyRecordedError,
    UnauthorizedError,
    WorkerNotRegisteredError,
)
from bot.tasks import service as task_service
from bot.users import repo as users_repo

router = Router()


class ExtendDeadlineStates(StatesGroup):
    awaiting_new_deadline = State()


def _parse_task_command(message: Message) -> tuple[int | None, str]:
    assignee_id: int | None = None
    for entity in (message.entities or []):
        if entity.type == "text_mention" and entity.user:
            assignee_id = entity.user.id
            break

    text = message.text or ""
    parts = text.split(maxsplit=1)
    body = parts[1] if len(parts) > 1 else ""
    return assignee_id, body


def _parse_callback_data(data: str) -> tuple[str, uuid.UUID, str, str]:
    """Parse 'action:task_id:reminder_id:outcome_id' from callback data."""
    parts = data.split(":", 3)
    action = parts[0]
    task_id = uuid.UUID(parts[1]) if len(parts) > 1 else uuid.UUID(int=0)
    reminder_id = parts[2] if len(parts) > 2 else ""
    outcome_id = parts[3] if len(parts) > 3 else ""
    return action, task_id, reminder_id, outcome_id


@router.message(Command("task"))
async def handle_task_command(
    message: Message, session: AsyncSession, bot: Bot | None = None
) -> None:
    if message.chat.id != settings.MASTER_GROUP_CHAT_ID:
        return

    assignee_mention_id, body = _parse_task_command(message)
    parts = body.rsplit(None, 1)
    title = parts[0].strip() if len(parts) > 1 else body
    raw_deadline = parts[1] if len(parts) > 1 else body

    try:
        task = await task_service.create_task(
            session=session,
            scheduler=None,
            bot=bot,
            session_factory=None,
            caller_telegram_id=message.from_user.id if message.from_user else 0,
            assignee_mention_id=assignee_mention_id,
            title=title or body,
            raw_deadline=raw_deadline or body,
            config=settings,
        )
    except UnauthorizedError:
        await message.answer("You are not authorized to assign tasks to others.")
        return
    except (DeadlineParseError, DeadlineInPastError):
        await message.answer(
            "I couldn't parse the deadline. Please rephrase with a clearer time reference."
        )
        return
    except WorkerNotRegisteredError:
        await message.answer(
            "The named person must start the bot in private before tasks can be assigned to them."
        )
        return

    worker = await users_repo.get_by_id(session, task.assignee_id)
    if worker and bot:
        await bot.send_message(
            chat_id=worker.telegram_id,
            text=f"You have been assigned a new task: {task.title}",
        )

    is_self_commit = assignee_mention_id is None
    if is_self_commit:
        if bot and message.from_user:
            await bot.send_message(
                chat_id=settings.MASTER_TELEGRAM_ID,
                text=f"New self-commitment from {message.from_user.full_name}: {task.title}",
            )
        await message.answer(f"Task recorded: {task.title}")
    else:
        worker_name = worker.display_name if worker else "Worker"
        await message.answer(f"Task assigned to {worker_name}: {task.title}")


@router.callback_query(F.data.startswith("done:"))
async def handle_done_callback(
    callback: CallbackQuery, session: AsyncSession, bot: Bot | None = None
) -> None:
    if callback.from_user.id != settings.MASTER_TELEGRAM_ID:
        return

    _, task_id, reminder_id, outcome_id = _parse_callback_data(callback.data or "")
    try:
        await task_service.record_done(session, None, task_id, reminder_id, outcome_id)
        await callback.answer("Outcome recorded: Done ✅")
    except OutcomeAlreadyRecordedError:
        await callback.answer("Outcome already recorded or prompt is no longer active.")


@router.callback_query(F.data.startswith("failed:"))
async def handle_failed_callback(
    callback: CallbackQuery, session: AsyncSession, bot: Bot | None = None
) -> None:
    if callback.from_user.id != settings.MASTER_TELEGRAM_ID:
        return

    _, task_id, reminder_id, outcome_id = _parse_callback_data(callback.data or "")
    try:
        task = await task_service.record_failed(session, None, task_id, reminder_id, outcome_id)
        await callback.answer("Outcome recorded: Failed ❌")
        worker = await users_repo.get_by_id(session, task.assignee_id)
        if worker and bot:
            text = notif_service.build_failed_notification_text(task)
            await bot.send_message(chat_id=worker.telegram_id, text=text)
    except OutcomeAlreadyRecordedError:
        await callback.answer("Outcome already recorded or prompt is no longer active.")


@router.callback_query(F.data.startswith("extended:"))
async def handle_extended_callback(
    callback: CallbackQuery, session: AsyncSession, state: FSMContext, bot: Bot | None = None
) -> None:
    if callback.from_user.id != settings.MASTER_TELEGRAM_ID:
        return

    _, task_id, reminder_id, outcome_id = _parse_callback_data(callback.data or "")
    from bot.tasks import repo as tasks_repo

    task = await tasks_repo.get_by_id(session, task_id)
    if task is None or task.status != "pending":
        await callback.answer("Outcome already recorded or prompt is no longer active.")
        return

    await state.set_state(ExtendDeadlineStates.awaiting_new_deadline)
    await state.update_data(
        task_id=str(task_id), reminder_id=reminder_id, outcome_id=outcome_id
    )
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.reply(
            "Please enter the new deadline for the extended task (e.g. 'tomorrow at 5pm'):"
        )


@router.message(Command("tasks"))
async def handle_tasks_command(message: Message, session: AsyncSession) -> None:
    assignee_tg_id = message.from_user.id if message.from_user else 0
    for entity in (message.entities or []):
        if entity.type == "text_mention" and entity.user:
            if message.from_user and message.from_user.id == settings.MASTER_TELEGRAM_ID:
                assignee_tg_id = entity.user.id
            break

    tasks = await task_service.get_open_tasks_for_worker(session, assignee_tg_id)
    if not tasks:
        await message.answer("No open tasks.")
        return

    tz = settings.MASTER_TIMEZONE
    from zoneinfo import ZoneInfo

    lines = []
    for t in tasks:
        deadline_str = t.deadline.astimezone(ZoneInfo(tz)).strftime("%Y-%m-%d %H:%M %Z")
        lines.append(f"• {t.title} — due {deadline_str}")
    await message.answer("\n".join(lines))


@router.message(ExtendDeadlineStates.awaiting_new_deadline)
async def handle_extend_deadline_input(
    message: Message, session: AsyncSession, state: FSMContext, bot: Bot | None = None
) -> None:
    data = await state.get_data()
    task_id = uuid.UUID(data["task_id"])
    reminder_id = data.get("reminder_id", "")
    outcome_id = data.get("outcome_id", "")

    try:
        task = await task_service.record_extended(
            session=session,
            scheduler=None,
            bot=bot,
            session_factory=None,
            task_id=task_id,
            raw_new_deadline=message.text or "",
            config=settings,
            reminder_job_id=reminder_id,
            outcome_job_id=outcome_id,
        )
        await state.clear()
        worker = await users_repo.get_by_id(session, task.assignee_id)
        if worker and bot:
            from bot.tasks import repo as tasks_repo

            refreshed = await tasks_repo.get_by_id(session, task_id)
            text = notif_service.build_extended_notification_text(
                task, refreshed.deadline if refreshed else task.deadline, settings.MASTER_TIMEZONE
            )
            await bot.send_message(chat_id=worker.telegram_id, text=text)
        await message.answer("Extension recorded. The accountability loop has restarted.")
    except DeadlineTooSoonError:
        await message.answer(
            "The new deadline must be at least 5 minutes in the future. Please re-enter:"
        )
    except DeadlineParseError:
        await message.answer(
            "I couldn't understand that deadline. Please try again with a clearer time reference:"
        )
