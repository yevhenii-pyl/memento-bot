"""APScheduler job functions — all scheduler callbacks live here (CLAUDE.md)."""
import logging
import time
import uuid

from bot.config import settings
from bot.notifications import service as notif_service
from bot.tasks import repo as tasks_repo
from bot.users import repo as users_repo

logger = logging.getLogger(__name__)


async def reminder_job(bot, task_id: str, session_factory) -> None:
    """Send a pre-deadline DM to the Worker; no-op if task is no longer open."""
    async with session_factory() as session:
        task = await tasks_repo.get_by_id(session, uuid.UUID(task_id))
        if task is None or task.status != "open":
            logger.info("reminder_job: task %s not open, skipping", task_id)
            return

        worker = await users_repo.get_by_id(session, task.assignee_id)
        if worker is None:
            logger.error("reminder_job: worker not found for task %s", task_id)
            return

        text = notif_service.build_reminder_text(
            task, worker.display_name, settings.MASTER_TIMEZONE
        )
        try:
            fire_ts = time.time()
            await bot.send_message(chat_id=worker.telegram_id, text=text)
            logger.info("reminder_job: sent reminder for task %s at %.3f", task_id, fire_ts)
        except Exception:
            logger.exception("reminder_job: DM delivery failed for task %s", task_id)


async def outcome_prompt_job(bot, task_id: str, session_factory) -> None:
    """Send outcome prompt to MASTER only; no-op if task is already resolved."""
    async with session_factory() as session:
        task = await tasks_repo.get_by_id(session, uuid.UUID(task_id))
        if task is None or task.status not in ("open", "pending"):
            logger.info("outcome_prompt_job: task %s already resolved, skipping", task_id)
            return

        await tasks_repo.set_pending(session, task.id)

        worker = await users_repo.get_by_id(session, task.assignee_id)
        worker_name = worker.display_name if worker else "Unknown"

        text = notif_service.build_outcome_prompt_text(
            task, worker_name, settings.MASTER_TIMEZONE
        )
        keyboard = notif_service.build_outcome_keyboard(task.id)
        try:
            fire_ts = time.time()
            await bot.send_message(
                chat_id=settings.MASTER_TELEGRAM_ID, text=text, reply_markup=keyboard
            )
            logger.info(
                "outcome_prompt_job: sent prompt for task %s at %.3f", task_id, fire_ts
            )
        except Exception:
            logger.exception("outcome_prompt_job: delivery failed for task %s", task_id)
