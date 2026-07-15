"""T11 unit tests — task creation handler."""
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from bot.shared.exceptions import (
    DeadlineInPastError,
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
    use_text_mention: bool = True,
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
        if use_text_mention:
            entity = MagicMock()
            entity.type = "text_mention"
            entity.user = MagicMock()
            entity.user.id = mention_id
            entity.offset = text.index("@") if "@" in text else 6
            entity.length = len("@Worker")
            msg.entities = [entity]
        else:
            entity = MagicMock()
            entity.type = "mention"
            entity.offset = text.index("@") if "@" in text else 6
            entity.length = len("@Worker")
            msg.entities = [entity]
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


def _make_worker() -> MagicMock:
    w = MagicMock()
    w.telegram_id = WORKER_TG_ID
    w.display_name = "Worker"
    return w


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
    worker_user = _make_worker()

    monkeypatch.setattr(f"{_SVC}.task_service.create_task", AsyncMock(return_value=task))
    monkeypatch.setattr(f"{_SVC}.users_repo.get_by_id", AsyncMock(return_value=worker_user))

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
async def test_task_command_deadline_in_past_gets_distinct_message(mock_settings, monkeypatch):
    """F4: DeadlineInPastError must produce a distinct 'in the past' reply."""
    from bot.tasks.handler import handle_task_command

    mock_settings.MASTER_GROUP_CHAT_ID = GROUP_CHAT_ID
    mock_settings.MASTER_TELEGRAM_ID = MASTER_TG_ID
    mock_settings.MASTER_TIMEZONE = "UTC"

    monkeypatch.setattr(
        f"{_SVC}.task_service.create_task",
        AsyncMock(side_effect=DeadlineInPastError("past")),
    )

    msg = _make_message(text="/task report yesterday")
    await handle_task_command(msg, session=AsyncMock(), bot=AsyncMock())

    msg.answer.assert_awaited_once()
    reply_text: str = msg.answer.call_args.args[0].lower()
    assert "past" in reply_text, f"Expected 'past' in reply but got: {reply_text!r}"


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


@patch(f"{_SVC}.settings")
async def test_task_command_passes_scheduler_to_service(mock_settings, monkeypatch):
    """F1: handler must forward real scheduler from workflow_data, not None."""
    from bot.tasks.handler import handle_task_command

    mock_settings.MASTER_GROUP_CHAT_ID = GROUP_CHAT_ID
    mock_settings.MASTER_TELEGRAM_ID = MASTER_TG_ID
    mock_settings.MASTER_TIMEZONE = "UTC"

    task = _make_task()
    worker_user = _make_worker()
    fake_scheduler = MagicMock()
    captured: list = []

    async def capture_create(**kwargs):
        captured.append(kwargs.get("scheduler"))
        return task

    monkeypatch.setattr(f"{_SVC}.task_service.create_task", capture_create)
    monkeypatch.setattr(f"{_SVC}.users_repo.get_by_id", AsyncMock(return_value=worker_user))

    msg = _make_message(mention_id=WORKER_TG_ID)
    await handle_task_command(
        msg, session=AsyncMock(), bot=AsyncMock(),
        scheduler=fake_scheduler, session_factory=AsyncMock(),
    )

    assert captured, "create_task was never called"
    assert captured[0] is fake_scheduler, "scheduler must not be None"


@patch(f"{_SVC}.settings")
async def test_task_command_mention_entity_resolves_via_get_chat(mock_settings, monkeypatch):
    """F3: public @mention (type='mention', no .user) must be resolved via bot.get_chat()."""
    from bot.tasks.handler import handle_task_command

    mock_settings.MASTER_GROUP_CHAT_ID = GROUP_CHAT_ID
    mock_settings.MASTER_TELEGRAM_ID = MASTER_TG_ID
    mock_settings.MASTER_TIMEZONE = "UTC"

    task = _make_task()
    worker_user = _make_worker()
    fake_chat = MagicMock()
    fake_chat.id = WORKER_TG_ID

    monkeypatch.setattr(f"{_SVC}.task_service.create_task", AsyncMock(return_value=task))
    monkeypatch.setattr(f"{_SVC}.users_repo.get_by_id", AsyncMock(return_value=worker_user))

    bot = AsyncMock()
    bot.get_chat = AsyncMock(return_value=fake_chat)

    msg = _make_message(mention_id=WORKER_TG_ID, use_text_mention=False)
    await handle_task_command(msg, session=AsyncMock(), bot=bot)

    bot.get_chat.assert_awaited_once()
    msg.answer.assert_awaited()


@patch(f"{_SVC}.settings")
async def test_task_command_multiword_deadline_body_split(mock_settings, monkeypatch):
    """S6: 'report by tomorrow 9am' must split into title='report', deadline includes 'tomorrow'."""
    from bot.tasks.handler import handle_task_command

    mock_settings.MASTER_GROUP_CHAT_ID = GROUP_CHAT_ID
    mock_settings.MASTER_TELEGRAM_ID = MASTER_TG_ID
    mock_settings.MASTER_TIMEZONE = "UTC"

    task = _make_task()
    captured: list[dict] = []

    async def capture_create(**kwargs):
        captured.append(kwargs)
        return task

    monkeypatch.setattr(f"{_SVC}.task_service.create_task", capture_create)
    monkeypatch.setattr(f"{_SVC}.users_repo.get_by_id", AsyncMock(return_value=_make_worker()))

    msg = _make_message(text="/task report by tomorrow 9am", mention_id=None)
    await handle_task_command(msg, session=AsyncMock(), bot=AsyncMock())

    assert captured, "create_task was never called"
    title = captured[0].get("title", "")
    raw_deadline = captured[0].get("raw_deadline", "")
    assert title == "report", f"Expected title='report', got {title!r}"
    assert "tomorrow" in raw_deadline, f"Expected 'tomorrow' in raw_deadline, got {raw_deadline!r}"
