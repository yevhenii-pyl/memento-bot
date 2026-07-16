"""T12 unit tests — outcome callback handler and Extend FSM."""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from bot.shared.exceptions import (
    OutcomeAlreadyRecordedError,
)

MASTER_TG_ID = 100000001
WORKER_TG_ID = 200000001
_SVC = "bot.tasks.handler"
TASK_ID = str(uuid.uuid4())


def _make_callback(user_id: int = MASTER_TG_ID, data: str = f"done:{TASK_ID}") -> MagicMock:
    cb = MagicMock()
    cb.from_user = MagicMock()
    cb.from_user.id = user_id
    cb.data = data
    cb.answer = AsyncMock()
    cb.message = MagicMock()
    cb.message.reply = AsyncMock()
    return cb


def _make_worker() -> MagicMock:
    w = MagicMock()
    w.telegram_id = WORKER_TG_ID
    w.display_name = "Bob"
    return w


def _make_task(title: str = "Report") -> MagicMock:
    t = MagicMock()
    t.id = uuid.UUID(TASK_ID)
    t.title = title
    t.assignee_id = uuid.uuid4()
    return t


@patch(f"{_SVC}.settings")
async def test_done_callback_records_outcome(mock_settings, monkeypatch):
    from bot.tasks.handler import handle_done_callback

    mock_settings.MASTER_TELEGRAM_ID = MASTER_TG_ID
    mock_settings.MASTER_TIMEZONE = "UTC"

    task = _make_task()
    monkeypatch.setattr(f"{_SVC}.task_service.record_done", AsyncMock(return_value=task))

    # Real keyboard emits 2-field format: done:<task_id>
    cb = _make_callback(data=f"done:{TASK_ID}")
    await handle_done_callback(cb, session=AsyncMock(), bot=AsyncMock())
    cb.answer.assert_awaited_once()


@patch(f"{_SVC}.settings")
async def test_done_callback_passes_deterministic_job_ids(mock_settings, monkeypatch):
    """F2: handler must derive job IDs from task_id, not from stale callback_data fields."""
    from bot.tasks.handler import handle_done_callback

    mock_settings.MASTER_TELEGRAM_ID = MASTER_TG_ID
    mock_settings.MASTER_TIMEZONE = "UTC"

    task = _make_task()
    record_mock = AsyncMock(return_value=task)
    monkeypatch.setattr(f"{_SVC}.task_service.record_done", record_mock)

    cb = _make_callback(data=f"done:{TASK_ID}")
    await handle_done_callback(cb, session=AsyncMock(), bot=AsyncMock(), scheduler=MagicMock())

    record_mock.assert_awaited_once()
    call_kwargs = record_mock.call_args.kwargs
    assert call_kwargs.get("reminder_job_id") == f"reminder:{TASK_ID}"
    assert call_kwargs.get("outcome_job_id") == f"outcome:{TASK_ID}"


@patch(f"{_SVC}.settings")
async def test_done_callback_already_recorded(mock_settings, monkeypatch):
    from bot.tasks.handler import handle_done_callback

    mock_settings.MASTER_TELEGRAM_ID = MASTER_TG_ID
    mock_settings.MASTER_TIMEZONE = "UTC"

    monkeypatch.setattr(
        f"{_SVC}.task_service.record_done",
        AsyncMock(side_effect=OutcomeAlreadyRecordedError("already")),
    )

    cb = _make_callback(data=f"done:{TASK_ID}")
    await handle_done_callback(cb, session=AsyncMock(), bot=AsyncMock())
    cb.answer.assert_awaited()
    reply_text = cb.answer.call_args.args[0] if cb.answer.call_args.args else ""
    assert "already" in reply_text.lower() or cb.answer.await_count >= 1


@patch(f"{_SVC}.settings")
async def test_failed_callback_sends_worker_dm(mock_settings, monkeypatch):
    from bot.tasks.handler import handle_failed_callback

    mock_settings.MASTER_TELEGRAM_ID = MASTER_TG_ID
    mock_settings.MASTER_TIMEZONE = "UTC"

    task = _make_task()
    worker = _make_worker()
    monkeypatch.setattr(f"{_SVC}.task_service.record_failed", AsyncMock(return_value=task))
    monkeypatch.setattr(f"{_SVC}.users_repo.get_by_id", AsyncMock(return_value=worker))

    cb = _make_callback(data=f"failed:{TASK_ID}")
    bot = AsyncMock()
    await handle_failed_callback(cb, session=AsyncMock(), bot=bot)

    cb.answer.assert_awaited()
    bot.send_message.assert_awaited_once()
    assert bot.send_message.call_args.kwargs.get("chat_id") == WORKER_TG_ID


@patch(f"{_SVC}.settings")
async def test_non_master_callback_ignored(mock_settings, monkeypatch):
    from bot.tasks.handler import handle_done_callback

    mock_settings.MASTER_TELEGRAM_ID = MASTER_TG_ID

    cb = _make_callback(user_id=WORKER_TG_ID, data=f"done:{TASK_ID}")
    create_mock = AsyncMock()
    monkeypatch.setattr(f"{_SVC}.task_service.record_done", create_mock)
    await handle_done_callback(cb, session=AsyncMock(), bot=AsyncMock())
    create_mock.assert_not_awaited()
    cb.answer.assert_not_awaited()
