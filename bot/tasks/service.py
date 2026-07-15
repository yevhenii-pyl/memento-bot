import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from bot.shared import claude_client
from bot.shared.exceptions import (
    DeadlineInPastError,
    DeadlineParseError,
    DeadlineTooSoonError,
    OutcomeAlreadyRecordedError,
    UnauthorizedError,
    WorkerNotRegisteredError,
)
from bot.shared.scheduler import cancel_task_jobs, reschedule_task_jobs, schedule_task_jobs
from bot.tasks import repo as tasks_repo
from bot.tasks.models import Task
from bot.users import repo as users_repo

_MIN_EXTEND_LEAD = timedelta(minutes=5)


async def create_task(
    session: AsyncSession,
    scheduler,
    bot,
    session_factory,
    caller_telegram_id: int,
    assignee_mention_id: int | None,
    title: str,
    raw_deadline: str,
    config,
) -> Task:
    assignee_telegram_id = (
        assignee_mention_id if assignee_mention_id is not None else caller_telegram_id
    )

    if assignee_telegram_id != caller_telegram_id:
        if caller_telegram_id != config.MASTER_TELEGRAM_ID:
            raise UnauthorizedError("Only the Master may assign tasks to others.")

    assignee = await users_repo.get_by_telegram_id(session, assignee_telegram_id)
    if assignee is None:
        raise WorkerNotRegisteredError(
            f"User {assignee_telegram_id} must start the bot in private first."
        )

    master = await users_repo.get_by_telegram_id(session, config.MASTER_TELEGRAM_ID)

    deadline = await claude_client.parse_deadline(raw_deadline)
    if deadline is None:
        raise DeadlineParseError("Could not parse a deadline from the provided text.")
    if deadline <= datetime.now(UTC):
        raise DeadlineInPastError("The deadline must be in the future.")

    task = await tasks_repo.create_task(
        session,
        assignee_id=assignee.id,
        overseer_id=master.id if master is not None else assignee.id,
        title=title,
        deadline=deadline,
    )
    schedule_task_jobs(scheduler, bot, session_factory, task)
    return task


async def get_open_tasks_for_worker(
    session: AsyncSession, assignee_telegram_id: int
) -> list[Task]:
    user = await users_repo.get_by_telegram_id(session, assignee_telegram_id)
    if user is None:
        return []
    return await tasks_repo.get_open_by_assignee(session, user.id)


async def record_done(
    session: AsyncSession,
    scheduler,
    task_id: uuid.UUID,
    reminder_job_id: str,
    outcome_job_id: str,
) -> Task:
    task = await tasks_repo.get_by_id(session, task_id)
    if task is None or task.status != "pending":
        raise OutcomeAlreadyRecordedError("Outcome already recorded or task not awaiting verdict.")
    await tasks_repo.update_status(session, task_id, "done")
    cancel_task_jobs(scheduler, reminder_job_id, outcome_job_id)
    return task


async def record_failed(
    session: AsyncSession,
    scheduler,
    task_id: uuid.UUID,
    reminder_job_id: str,
    outcome_job_id: str,
) -> Task:
    task = await tasks_repo.get_by_id(session, task_id)
    if task is None or task.status != "pending":
        raise OutcomeAlreadyRecordedError("Outcome already recorded or task not awaiting verdict.")
    await tasks_repo.update_status(session, task_id, "failed")
    cancel_task_jobs(scheduler, reminder_job_id, outcome_job_id)
    return task


async def record_extended(
    session: AsyncSession,
    scheduler,
    bot,
    session_factory,
    task_id: uuid.UUID,
    raw_new_deadline: str,
    config,
    reminder_job_id: str,
    outcome_job_id: str,
) -> Task:
    task = await tasks_repo.get_by_id(session, task_id)
    if task is None or task.status != "pending":
        raise OutcomeAlreadyRecordedError("Outcome already recorded or task not awaiting verdict.")

    new_deadline = await claude_client.parse_deadline(raw_new_deadline)
    if new_deadline is None:
        raise DeadlineParseError("Could not parse the new deadline.")
    if new_deadline <= datetime.now(UTC) + _MIN_EXTEND_LEAD:
        raise DeadlineTooSoonError("New deadline must be at least 5 minutes in the future.")

    await tasks_repo.record_extension(session, task_id, new_deadline)
    reschedule_task_jobs(scheduler, bot, session_factory, task, reminder_job_id, outcome_job_id)
    return task
