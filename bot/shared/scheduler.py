from datetime import UTC, datetime, timedelta

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot.config import settings

_REMINDER_LEAD = timedelta(minutes=5)
_IMMEDIATE_BUFFER = timedelta(seconds=1)


def create_scheduler() -> AsyncIOScheduler:
    sync_url = settings.DATABASE_URL.replace("+asyncpg", "")
    jobstores = {"default": SQLAlchemyJobStore(url=sync_url)}
    return AsyncIOScheduler(jobstores=jobstores)


def schedule_task_jobs(scheduler: AsyncIOScheduler, bot, session_factory, task) -> tuple[str, str]:
    """Register reminder (T-5min) and outcome (T) jobs. Returns (reminder_id, outcome_id)."""
    now = datetime.now(UTC)
    reminder_time = task.deadline - _REMINDER_LEAD
    if reminder_time <= now:
        reminder_time = now + _IMMEDIATE_BUFFER

    from bot.notifications.jobs import outcome_prompt_job, reminder_job

    task_id_str = str(task.id)
    reminder_id = f"reminder:{task_id_str}"
    outcome_id = f"outcome:{task_id_str}"

    scheduler.add_job(
        reminder_job,
        trigger="date",
        run_date=reminder_time,
        kwargs={"bot": bot, "task_id": task_id_str, "session_factory": session_factory},
        id=reminder_id,
        replace_existing=True,
    )
    scheduler.add_job(
        outcome_prompt_job,
        trigger="date",
        run_date=task.deadline,
        kwargs={"bot": bot, "task_id": task_id_str, "session_factory": session_factory},
        id=outcome_id,
        replace_existing=True,
    )
    return reminder_id, outcome_id


def cancel_task_jobs(
    scheduler: AsyncIOScheduler, reminder_job_id: str, outcome_job_id: str
) -> None:
    """Remove both jobs; tolerates already-removed IDs."""
    for job_id in (reminder_job_id, outcome_job_id):
        try:
            scheduler.remove_job(job_id)
        except Exception:
            pass


def reschedule_task_jobs(
    scheduler: AsyncIOScheduler,
    bot,
    session_factory,
    task,
    old_reminder_id: str,
    old_outcome_id: str,
) -> tuple[str, str]:
    """Cancel old jobs and schedule new ones for the updated task deadline."""
    cancel_task_jobs(scheduler, old_reminder_id, old_outcome_id)
    return schedule_task_jobs(scheduler, bot, session_factory, task)
