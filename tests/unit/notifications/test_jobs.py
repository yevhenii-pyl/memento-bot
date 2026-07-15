"""T06 unit tests — notification job functions."""
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from bot.notifications import jobs as notification_jobs

MASTER_TG_ID = 777000777
WORKER_TG_ID = 888000888
TASK_ID = str(uuid.uuid4())


def _make_task(status: str = "open") -> MagicMock:
    task = MagicMock()
    task.id = uuid.UUID(TASK_ID)
    task.title = "Deliver report"
    task.deadline = datetime.now(UTC) + timedelta(hours=1)
    task.status = status
    task.assignee_id = uuid.uuid4()
    return task


def _make_worker() -> MagicMock:
    worker = MagicMock()
    worker.telegram_id = WORKER_TG_ID
    worker.display_name = "Bob"
    return worker


def _make_session_factory():
    session = AsyncMock()

    @asynccontextmanager
    async def factory():
        yield session

    return factory, session


@patch("bot.notifications.jobs.settings")
async def test_reminder_job_sends_dm_to_worker(mock_settings):
    mock_settings.MASTER_TELEGRAM_ID = MASTER_TG_ID
    mock_settings.MASTER_TIMEZONE = "UTC"

    task = _make_task(status="open")
    worker = _make_worker()
    factory, session = _make_session_factory()
    bot = AsyncMock()

    with (
        patch("bot.notifications.jobs.tasks_repo.get_by_id", AsyncMock(return_value=task)),
        patch("bot.notifications.jobs.users_repo.get_by_id", AsyncMock(return_value=worker)),
    ):
        await notification_jobs.reminder_job(bot, TASK_ID, factory)

    bot.send_message.assert_awaited_once()
    call_kwargs = bot.send_message.call_args.kwargs
    assert call_kwargs.get("chat_id") == WORKER_TG_ID


@patch("bot.notifications.jobs.settings")
async def test_reminder_job_skips_when_not_open(mock_settings):
    mock_settings.MASTER_TELEGRAM_ID = MASTER_TG_ID
    mock_settings.MASTER_TIMEZONE = "UTC"

    task = _make_task(status="done")
    factory, session = _make_session_factory()
    bot = AsyncMock()

    with patch("bot.notifications.jobs.tasks_repo.get_by_id", AsyncMock(return_value=task)):
        await notification_jobs.reminder_job(bot, TASK_ID, factory)

    bot.send_message.assert_not_awaited()


@patch("bot.notifications.jobs.settings")
async def test_outcome_prompt_job_sends_to_master_only(mock_settings):
    mock_settings.MASTER_TELEGRAM_ID = MASTER_TG_ID
    mock_settings.MASTER_TIMEZONE = "UTC"

    task = _make_task(status="open")
    worker = _make_worker()
    factory, session = _make_session_factory()
    bot = AsyncMock()

    with (
        patch("bot.notifications.jobs.tasks_repo.get_by_id", AsyncMock(return_value=task)),
        patch("bot.notifications.jobs.tasks_repo.set_pending", AsyncMock()),
        patch("bot.notifications.jobs.users_repo.get_by_id", AsyncMock(return_value=worker)),
    ):
        await notification_jobs.outcome_prompt_job(bot, TASK_ID, factory)

    bot.send_message.assert_awaited_once()
    call_kwargs = bot.send_message.call_args.kwargs
    recipient = call_kwargs.get("chat_id")
    assert recipient == MASTER_TG_ID
    assert recipient != WORKER_TG_ID


@patch("bot.notifications.jobs.settings")
async def test_outcome_prompt_job_skips_when_resolved(mock_settings):
    mock_settings.MASTER_TELEGRAM_ID = MASTER_TG_ID
    mock_settings.MASTER_TIMEZONE = "UTC"

    task = _make_task(status="done")
    factory, session = _make_session_factory()
    bot = AsyncMock()

    with patch("bot.notifications.jobs.tasks_repo.get_by_id", AsyncMock(return_value=task)):
        await notification_jobs.outcome_prompt_job(bot, TASK_ID, factory)

    bot.send_message.assert_not_awaited()
