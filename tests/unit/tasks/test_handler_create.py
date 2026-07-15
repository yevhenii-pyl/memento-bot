"""T11 unit tests — task creation handler."""
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from bot.shared.exceptions import (
    DeadlineParseError,
    UnauthorizedError,
    WorkerNotRegisteredError,
)

MASTER_TG_ID = 100000001
WORKER_TG_ID = 200000001
GROUP_CHAT_ID = -300000001

_SVC = "bot.tasks.handler"


def _make_message(
    chat_id: int = GROUP_CHAT_ID,
    user_id: int = MASTER_TG_ID,
    text: str = "/task @Worker Build the report by tomorrow",
    mention_id: int | None = None,
) -> MagicMock:
    msg = MagicMock()
    msg.chat = MagicMock()
    msg.chat.id = chat_id
    msg.from_user = MagicMock()
    msg.from_user.id = user_id
    msg.from_user.full_name = "Master"
    msg.text = text
    msg.answer = AsyncMock()

    if mention_id is not None:
        entity = MagicMock()
        entity.type = "mention"
        entity.offset = text.index("@")
        entity.length = len("@Worker")
        mention_user = MagicMock()
        mention_user.id = mention_id
        text_mention_entity = MagicMock()
        text_mention_entity.type = "text_mention"
        text_mention_entity.user = mention_user
        text_mention_entity.offset = entity.offset
        text_mention_entity.length = entity.length
        msg.entities = [text_mention_entity]
    else:
        msg.entities = []

    return msg


def _make_task(worker_tg_id: int = WORKER_TG_ID) -> MagicMock:
    t = MagicMock()
    t.id = uuid.uuid4()
    t.title = "Build the report"
    t.deadline = datetime.now(UTC) + timedelta(hours=24)
    t.assignee_id = uuid.uuid4()
    return t


@patch(f"{_SVC}.settings")
async def test_task_command_ignored_outside_group_chat(mock_settings):
    from bot.tasks.handler import handle_task_command

    mock_settings.MASTER_GROUP_CHAT_ID = GROUP_CHAT_ID
    mock_settings.MASTER_TELEGRAM_ID = MASTER_TG_ID
    mock_settings.MASTER_TIMEZONE = "UTC"

    msg = _make_message(chat_id=-999999)
    await handle_task_command(msg, session=AsyncMock())
    msg.answer.assert_not_awaited()


@patch(f"{_SVC}.settings")
async def test_task_command_master_assign_happy_path(mock_settings, monkeypatch):
    from bot.tasks.handler import handle_task_command

    mock_settings.MASTER_GROUP_CHAT_ID = GROUP_CHAT_ID
    mock_settings.MASTER_TELEGRAM_ID = MASTER_TG_ID
    mock_settings.MASTER_TIMEZONE = "UTC"

    task = _make_task()
    worker_user = MagicMock()
    worker_user.telegram_id = WORKER_TG_ID

    monkeypatch.setattr(
        f"{_SVC}.task_service.create_task", AsyncMock(return_value=task)
    )
    monkeypatch.setattr(
        f"{_SVC}.users_repo.get_by_id", AsyncMock(return_value=worker_user)
    )

    msg = _make_message(mention_id=WORKER_TG_ID)
    bot = AsyncMock()
    await handle_task_command(msg, session=AsyncMock(), bot=bot)

    bot.send_message.assert_awaited()
    msg.answer.assert_awaited()


@patch(f"{_SVC}.settings")
async def test_task_command_unauthorized_error(mock_settings, monkeypatch):
    from bot.tasks.handler import handle_task_command

    mock_settings.MASTER_GROUP_CHAT_ID = GROUP_CHAT_ID
    mock_settings.MASTER_TELEGRAM_ID = MASTER_TG_ID
    mock_settings.MASTER_TIMEZONE = "UTC"

    monkeypatch.setattr(
        f"{_SVC}.task_service.create_task", AsyncMock(side_effect=UnauthorizedError("no"))
    )

    msg = _make_message(user_id=WORKER_TG_ID, mention_id=999999)
    await handle_task_command(msg, session=AsyncMock(), bot=AsyncMock())
    msg.answer.assert_awaited_once()


@patch(f"{_SVC}.settings")
async def test_task_command_deadline_parse_error(mock_settings, monkeypatch):
    from bot.tasks.handler import handle_task_command

    mock_settings.MASTER_GROUP_CHAT_ID = GROUP_CHAT_ID
    mock_settings.MASTER_TELEGRAM_ID = MASTER_TG_ID
    mock_settings.MASTER_TIMEZONE = "UTC"

    monkeypatch.setattr(
        f"{_SVC}.task_service.create_task", AsyncMock(side_effect=DeadlineParseError("bad"))
    )

    msg = _make_message()
    await handle_task_command(msg, session=AsyncMock(), bot=AsyncMock())
    msg.answer.assert_awaited_once()


@patch(f"{_SVC}.settings")
async def test_task_command_worker_not_registered(mock_settings, monkeypatch):
    from bot.tasks.handler import handle_task_command

    mock_settings.MASTER_GROUP_CHAT_ID = GROUP_CHAT_ID
    mock_settings.MASTER_TELEGRAM_ID = MASTER_TG_ID
    mock_settings.MASTER_TIMEZONE = "UTC"

    monkeypatch.setattr(
        f"{_SVC}.task_service.create_task",
        AsyncMock(side_effect=WorkerNotRegisteredError("not reg")),
    )

    msg = _make_message(mention_id=WORKER_TG_ID)
    await handle_task_command(msg, session=AsyncMock(), bot=AsyncMock())
    msg.answer.assert_awaited_once()
