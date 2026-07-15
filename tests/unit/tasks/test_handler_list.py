"""T13 unit tests — task listing handlers."""
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram.exceptions import TelegramAPIError

MASTER_TG_ID = 100000001
WORKER_TG_ID = 200000001
_SVC = "bot.tasks.handler"


def _make_message(
    user_id: int = WORKER_TG_ID,
    chat_type: str = "private",
    text: str = "/tasks",
    mention_id: int | None = None,
) -> MagicMock:
    msg = MagicMock()
    msg.from_user = MagicMock()
    msg.from_user.id = user_id
    msg.chat = MagicMock()
    msg.chat.type = chat_type
    msg.text = text
    msg.answer = AsyncMock()
    if mention_id:
        entity = MagicMock()
        entity.type = "text_mention"
        entity.user = MagicMock()
        entity.user.id = mention_id
        msg.entities = [entity]
    else:
        msg.entities = []
    return msg


def _make_task(title: str = "Build thing") -> MagicMock:
    t = MagicMock()
    t.id = uuid.uuid4()
    t.title = title
    t.deadline = datetime.now(UTC) + timedelta(hours=24)
    return t


@patch(f"{_SVC}.settings")
async def test_tasks_command_worker_lists_own_tasks(mock_settings, monkeypatch):
    from bot.tasks.handler import handle_tasks_command

    mock_settings.MASTER_TELEGRAM_ID = MASTER_TG_ID
    mock_settings.MASTER_TIMEZONE = "UTC"

    tasks = [_make_task("Write docs"), _make_task("Fix bug")]
    monkeypatch.setattr(
        f"{_SVC}.task_service.get_open_tasks_for_worker", AsyncMock(return_value=tasks)
    )

    msg = _make_message(user_id=WORKER_TG_ID)
    await handle_tasks_command(msg, session=AsyncMock())

    msg.answer.assert_awaited_once()
    reply_text = msg.answer.call_args.args[0]
    assert "Write docs" in reply_text
    assert "Fix bug" in reply_text


@patch(f"{_SVC}.settings")
async def test_tasks_command_no_open_tasks_reply(mock_settings, monkeypatch):
    from bot.tasks.handler import handle_tasks_command

    mock_settings.MASTER_TELEGRAM_ID = MASTER_TG_ID
    mock_settings.MASTER_TIMEZONE = "UTC"

    monkeypatch.setattr(
        f"{_SVC}.task_service.get_open_tasks_for_worker", AsyncMock(return_value=[])
    )

    msg = _make_message()
    await handle_tasks_command(msg, session=AsyncMock())

    msg.answer.assert_awaited_once()
    reply_text = msg.answer.call_args.args[0].lower()
    assert "no" in reply_text or "none" in reply_text or "empty" in reply_text


@patch(f"{_SVC}.settings")
async def test_tasks_command_master_views_worker_tasks(mock_settings, monkeypatch):
    from bot.tasks.handler import handle_tasks_command

    mock_settings.MASTER_TELEGRAM_ID = MASTER_TG_ID
    mock_settings.MASTER_TIMEZONE = "UTC"

    tasks = [_make_task("Worker task")]
    monkeypatch.setattr(
        f"{_SVC}.task_service.get_open_tasks_for_worker", AsyncMock(return_value=tasks)
    )

    msg = _make_message(user_id=MASTER_TG_ID, mention_id=WORKER_TG_ID, text="/tasks @Worker")
    await handle_tasks_command(msg, session=AsyncMock())

    msg.answer.assert_awaited_once()
    reply_text = msg.answer.call_args.args[0]
    assert "Worker task" in reply_text


@patch(f"{_SVC}.settings")
async def test_tasks_command_master_mention_entity_resolves(mock_settings, monkeypatch):
    """F7/F8: a 'mention' entity in /tasks must be resolved via bot.get_chat()."""
    from bot.tasks.handler import handle_tasks_command

    mock_settings.MASTER_TELEGRAM_ID = MASTER_TG_ID
    mock_settings.MASTER_TIMEZONE = "UTC"

    tasks = [_make_task("Worker task")]
    monkeypatch.setattr(
        f"{_SVC}.task_service.get_open_tasks_for_worker", AsyncMock(return_value=tasks)
    )

    text = "/tasks @Worker"
    entity = MagicMock()
    entity.type = "mention"
    entity.offset = text.index("@")
    entity.length = len("@Worker")

    msg = MagicMock()
    msg.from_user = MagicMock()
    msg.from_user.id = MASTER_TG_ID
    msg.text = text
    msg.entities = [entity]
    msg.answer = AsyncMock()

    fake_chat = MagicMock()
    fake_chat.id = WORKER_TG_ID
    bot = AsyncMock()
    bot.get_chat = AsyncMock(return_value=fake_chat)

    await handle_tasks_command(msg, session=AsyncMock(), bot=bot)

    bot.get_chat.assert_awaited_once_with("@Worker")
    msg.answer.assert_awaited_once()
    assert "Worker task" in msg.answer.call_args.args[0]


@patch(f"{_SVC}.settings")
async def test_tasks_command_worker_not_found_replies_error(mock_settings, monkeypatch):
    """F8: unresolvable @username must reply with worker-not-found message."""
    from bot.tasks.handler import handle_tasks_command

    mock_settings.MASTER_TELEGRAM_ID = MASTER_TG_ID
    mock_settings.MASTER_TIMEZONE = "UTC"

    text = "/tasks @Unknown"
    entity = MagicMock()
    entity.type = "mention"
    entity.offset = text.index("@")
    entity.length = len("@Unknown")

    msg = MagicMock()
    msg.from_user = MagicMock()
    msg.from_user.id = MASTER_TG_ID
    msg.text = text
    msg.entities = [entity]
    msg.answer = AsyncMock()

    bot = AsyncMock()
    bot.get_chat = AsyncMock(side_effect=TelegramAPIError(method=MagicMock(), message="not found"))

    await handle_tasks_command(msg, session=AsyncMock(), bot=bot)

    msg.answer.assert_awaited_once()
    reply_text = msg.answer.call_args.args[0].lower()
    assert "recognise" in reply_text or "not found" in reply_text or "unknown" in reply_text
