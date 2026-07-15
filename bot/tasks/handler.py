import re
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
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

_DEADLINE_KW = re.compile(r"\s+(by|until|before|in|at|due|on)\s+", re.IGNORECASE)


class ExtendDeadlineStates(StatesGroup):
    awaiting_new_deadline = State()


def _split_body(body: str) -> tuple[str, str]:
    """Split 'title <deadline_phrase>' on the first deadline keyword.

    Returns (body, body) when no keyword is found so the whole body is used as
    both title hint and raw_deadline — Claude decides what is parseable.
    """
    m = _DEADLINE_KW.search(body)
    if m:
        title = body[: m.start()].strip()
        deadline_raw = body[m.start() :].strip()
        return title or body, deadline_raw
    return body, body


def _failed_notification_text(task_title: str) -> str:
    return f'Your task "{task_title}" was marked as failed by the Master.'


def _extended_notification_text(task_title: str, deadline: datetime, timezone: str) -> str:
    dl = deadline.astimezone(ZoneInfo(timezone)).strftime("%Y-%m-%d %H:%M %Z")
    return f'Your task "{task_title}" deadline has been extended to {dl}.'


def _parse_task_command(
    message: Message,
) -> tuple[int | None, str | None, str]:
    """Return (telegram_id from text_mention, @username from mention, body after /cmd [mention])."""
    assignee_id: int | None = None
    mention_username: str | None = None
    text = message.text or ""

    for entity in message.entities or []:
        if entity.type == "text_mention" and entity.user:
            assignee_id = entity.user.id
            break
        if entity.type == "mention":
            mention_username = text[entity.offset : entity.offset + entity.length]
            break

    parts = text.split(maxsplit=1)
    body = parts[1] if len(parts) > 1 else ""
    if mention_username and body.startswith(mention_username):
        body = body[len(mention_username) :].strip()
    return assignee_id, mention_username, body


def _parse_callback_data(data: str) -> tuple[str, uuid.UUID]:
    """Parse 'action:task_id' — job IDs are derived deterministically from task_id."""
    parts = data.split(":", 1)
    action = parts[0]
    task_id = uuid.UUID(parts[1]) if len(parts) > 1 else uuid.UUID(int=0)
    return action, task_id


@router.message(Command("task"))
async def handle_task_command(
    message: Message,
    session: AsyncSession,
    bot: Bot | None = None,
    scheduler=None,
    session_factory=None,
) -> None:
    if message.chat.id != settings.MASTER_GROUP_CHAT_ID:
        return

    assignee_mention_id, mention_username, body = _parse_task_command(message)

    if mention_username is not None and assignee_mention_id is None:
        if bot is None:
            await message.answer(
                "The named person must start the bot in private before tasks can be assigned."
            )
            return
        try:
            chat = await bot.get_chat(mention_username)
            assignee_mention_id = chat.id
        except TelegramAPIError:
            await message.answer(
                "The named person must start the bot in private"
                " before tasks can be assigned to them."
            )
            return

    title, raw_deadline = _split_body(body)

    try:
        task = await task_service.create_task(
            session=session,
            scheduler=scheduler,
            bot=bot,
            session_factory=session_factory,
            caller_telegram_id=message.from_user.id if message.from_user else 0,
            assignee_mention_id=assignee_mention_id,
            title=title or body,
            raw_deadline=raw_deadline or body,
            config=settings,
        )
    except UnauthorizedError:
        await message.answer("You are not authorized to assign tasks to others.")
        return
    except DeadlineInPastError:
        await message.answer(
            "That deadline is in the past. Please provide a future deadline."
        )
        return
    except DeadlineParseError:
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
    callback: CallbackQuery,
    session: AsyncSession,
    bot: Bot | None = None,
    scheduler=None,
) -> None:
    if callback.from_user.id != settings.MASTER_TELEGRAM_ID:
        return

    _, task_id = _parse_callback_data(callback.data or "")
    reminder_job_id = f"reminder:{task_id}"
    outcome_job_id = f"outcome:{task_id}"
    try:
        await task_service.record_done(
            session=session,
            scheduler=scheduler,
            task_id=task_id,
            reminder_job_id=reminder_job_id,
            outcome_job_id=outcome_job_id,
        )
        await callback.answer("Outcome recorded: Done ✅")
    except OutcomeAlreadyRecordedError:
        await callback.answer("Outcome already recorded or prompt is no longer active.")


@router.callback_query(F.data.startswith("failed:"))
async def handle_failed_callback(
    callback: CallbackQuery,
    session: AsyncSession,
    bot: Bot | None = None,
    scheduler=None,
) -> None:
    if callback.from_user.id != settings.MASTER_TELEGRAM_ID:
        return

    _, task_id = _parse_callback_data(callback.data or "")
    reminder_job_id = f"reminder:{task_id}"
    outcome_job_id = f"outcome:{task_id}"
    try:
        task = await task_service.record_failed(
            session=session,
            scheduler=scheduler,
            task_id=task_id,
            reminder_job_id=reminder_job_id,
            outcome_job_id=outcome_job_id,
        )
        await callback.answer("Outcome recorded: Failed ❌")
        worker = await users_repo.get_by_id(session, task.assignee_id)
        if worker and bot:
            await bot.send_message(
                chat_id=worker.telegram_id,
                text=_failed_notification_text(task.title),
            )
    except OutcomeAlreadyRecordedError:
        await callback.answer("Outcome already recorded or prompt is no longer active.")


@router.callback_query(F.data.startswith("extended:"))
async def handle_extended_callback(
    callback: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
    bot: Bot | None = None,
    scheduler=None,
) -> None:
    if callback.from_user.id != settings.MASTER_TELEGRAM_ID:
        return

    _, task_id = _parse_callback_data(callback.data or "")
    from bot.tasks import repo as tasks_repo

    task = await tasks_repo.get_by_id(session, task_id)
    if task is None or task.status != "pending":
        await callback.answer("Outcome already recorded or prompt is no longer active.")
        return

    await state.set_state(ExtendDeadlineStates.awaiting_new_deadline)
    await state.update_data(task_id=str(task_id))
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.reply(
            "Please enter the new deadline for the extended task (e.g. 'tomorrow at 5pm'):"
        )


@router.message(Command("tasks"))
async def handle_tasks_command(
    message: Message,
    session: AsyncSession,
    bot: Bot | None = None,
) -> None:
    assignee_tg_id = message.from_user.id if message.from_user else 0
    text = message.text or ""

    for entity in message.entities or []:
        if message.from_user and message.from_user.id == settings.MASTER_TELEGRAM_ID:
            if entity.type == "text_mention" and entity.user:
                assignee_tg_id = entity.user.id
                break
            if entity.type == "mention":
                username = text[entity.offset : entity.offset + entity.length]
                if bot is None:
                    await message.answer("I don't recognise that user.")
                    return
                try:
                    chat = await bot.get_chat(username)
                    assignee_tg_id = chat.id
                except TelegramAPIError:
                    await message.answer("I don't recognise that user.")
                    return
                break

    tasks = await task_service.get_open_tasks_for_worker(session, assignee_tg_id)
    if not tasks:
        await message.answer("No open tasks.")
        return

    tz = settings.MASTER_TIMEZONE
    lines = []
    for t in tasks:
        deadline_str = t.deadline.astimezone(ZoneInfo(tz)).strftime("%Y-%m-%d %H:%M %Z")
        lines.append(f"• {t.title} — due {deadline_str}")
    await message.answer("\n".join(lines))


@router.message(ExtendDeadlineStates.awaiting_new_deadline)
async def handle_extend_deadline_input(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    bot: Bot | None = None,
    scheduler=None,
    session_factory=None,
) -> None:
    data = await state.get_data()
    task_id = uuid.UUID(data["task_id"])
    reminder_job_id = f"reminder:{task_id}"
    outcome_job_id = f"outcome:{task_id}"

    try:
        task = await task_service.record_extended(
            session=session,
            scheduler=scheduler,
            bot=bot,
            session_factory=session_factory,
            task_id=task_id,
            raw_new_deadline=message.text or "",
            config=settings,
            reminder_job_id=reminder_job_id,
            outcome_job_id=outcome_job_id,
        )
        await state.clear()
        worker = await users_repo.get_by_id(session, task.assignee_id)
        if worker and bot:
            from bot.tasks import repo as tasks_repo

            refreshed = await tasks_repo.get_by_id(session, task_id)
            new_deadline = refreshed.deadline if refreshed else task.deadline
            tz = settings.MASTER_TIMEZONE
            await bot.send_message(
                chat_id=worker.telegram_id,
                text=_extended_notification_text(task.title, new_deadline, tz),
            )
        await message.answer("Extension recorded. The accountability loop has restarted.")
    except DeadlineTooSoonError:
        await message.answer(
            "The new deadline must be at least 5 minutes in the future. Please re-enter:"
        )
    except DeadlineParseError:
        await message.answer(
            "I couldn't understand that deadline. Please try again with a clearer time reference:"
        )
