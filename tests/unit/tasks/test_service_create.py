"""T08 unit tests — task service creation and listing."""
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from bot.shared.exceptions import (
    DeadlineInPastError,
    DeadlineParseError,
    UnauthorizedError,
    WorkerNotRegisteredError,
)
from bot.tasks import service as task_service

MASTER_TG_ID = 100000001
WORKER_TG_ID = 200000001

_SVC = "bot.tasks.service"


def _patch(mp, attr, **kw):
    mp.setattr(f"{_SVC}.{attr}", AsyncMock(**kw))


def _make_config():
    cfg = MagicMock()
    cfg.MASTER_TELEGRAM_ID = MASTER_TG_ID
    cfg.MASTER_TIMEZONE = "UTC"
    return cfg


def _make_user(telegram_id: int) -> MagicMock:
    u = MagicMock()
    u.id = uuid.uuid4()
    u.telegram_id = telegram_id
    u.display_name = "Test User"
    return u


def _make_task() -> MagicMock:
    t = MagicMock()
    t.id = uuid.uuid4()
    t.title = "Build report"
    t.deadline = datetime.now(UTC) + timedelta(hours=2)
    return t


async def test_create_task_master_assigns_to_worker(monkeypatch):
    worker = _make_user(WORKER_TG_ID)
    master = _make_user(MASTER_TG_ID)
    task = _make_task()
    deadline = datetime.now(UTC) + timedelta(hours=2)

    monkeypatch.setattr(
        f"{_SVC}.users_repo.get_by_telegram_id",
        AsyncMock(side_effect=[worker, master]),
    )
    _patch(monkeypatch, "tasks_repo.create_task", return_value=task)
    _patch(monkeypatch, "claude_client.parse_deadline", return_value=deadline)
    monkeypatch.setattr(f"{_SVC}.schedule_task_jobs", MagicMock(return_value=("r1", "o1")))

    result = await task_service.create_task(
        AsyncMock(), MagicMock(), AsyncMock(), AsyncMock(),
        MASTER_TG_ID, WORKER_TG_ID, "Build report", "tomorrow 5pm", _make_config(),
    )
    assert result is task


async def test_create_task_worker_self_commit(monkeypatch):
    worker = _make_user(WORKER_TG_ID)
    master = _make_user(MASTER_TG_ID)
    task = _make_task()
    deadline = datetime.now(UTC) + timedelta(hours=2)

    monkeypatch.setattr(
        f"{_SVC}.users_repo.get_by_telegram_id",
        AsyncMock(side_effect=[worker, master]),
    )
    _patch(monkeypatch, "tasks_repo.create_task", return_value=task)
    _patch(monkeypatch, "claude_client.parse_deadline", return_value=deadline)
    monkeypatch.setattr(f"{_SVC}.schedule_task_jobs", MagicMock(return_value=("r1", "o1")))

    result = await task_service.create_task(
        AsyncMock(), MagicMock(), AsyncMock(), AsyncMock(),
        WORKER_TG_ID, None, "My commitment", "by EOD", _make_config(),
    )
    assert result is task


async def test_create_task_unauthorized_assign(monkeypatch):
    with pytest.raises(UnauthorizedError):
        await task_service.create_task(
            AsyncMock(), MagicMock(), AsyncMock(), AsyncMock(),
            WORKER_TG_ID, 999999, "task", "deadline", _make_config(),
        )


async def test_create_task_unresolvable_deadline(monkeypatch):
    worker = _make_user(WORKER_TG_ID)
    _patch(monkeypatch, "users_repo.get_by_telegram_id", return_value=worker)
    _patch(monkeypatch, "claude_client.parse_deadline", return_value=None)

    with pytest.raises(DeadlineParseError):
        await task_service.create_task(
            AsyncMock(), MagicMock(), AsyncMock(), AsyncMock(),
            MASTER_TG_ID, WORKER_TG_ID, "task", "gibberish", _make_config(),
        )


async def test_create_task_past_deadline(monkeypatch):
    worker = _make_user(WORKER_TG_ID)
    past = datetime.now(UTC) - timedelta(hours=1)
    _patch(monkeypatch, "users_repo.get_by_telegram_id", return_value=worker)
    _patch(monkeypatch, "claude_client.parse_deadline", return_value=past)

    with pytest.raises(DeadlineInPastError):
        await task_service.create_task(
            AsyncMock(), MagicMock(), AsyncMock(), AsyncMock(),
            MASTER_TG_ID, WORKER_TG_ID, "task", "yesterday", _make_config(),
        )


async def test_create_task_unregistered_worker(monkeypatch):
    _patch(monkeypatch, "users_repo.get_by_telegram_id", return_value=None)

    with pytest.raises(WorkerNotRegisteredError):
        await task_service.create_task(
            AsyncMock(), MagicMock(), AsyncMock(), AsyncMock(),
            MASTER_TG_ID, WORKER_TG_ID, "task", "tomorrow", _make_config(),
        )


async def test_get_open_tasks_returns_list(monkeypatch):
    worker = _make_user(WORKER_TG_ID)
    tasks = [_make_task(), _make_task()]
    _patch(monkeypatch, "users_repo.get_by_telegram_id", return_value=worker)
    _patch(monkeypatch, "tasks_repo.get_open_by_assignee", return_value=tasks)

    result = await task_service.get_open_tasks_for_worker(AsyncMock(), WORKER_TG_ID)
    assert result == tasks


async def test_get_open_tasks_returns_empty_for_unknown_user(monkeypatch):
    _patch(monkeypatch, "users_repo.get_by_telegram_id", return_value=None)

    result = await task_service.get_open_tasks_for_worker(AsyncMock(), 999999)
    assert result == []


async def test_create_task_raises_when_master_unregistered(monkeypatch):
    """S5: silently fabricating overseer must be replaced with a hard failure."""
    worker = _make_user(WORKER_TG_ID)
    deadline = datetime.now(UTC) + timedelta(hours=2)
    monkeypatch.setattr(
        f"{_SVC}.users_repo.get_by_telegram_id",
        AsyncMock(side_effect=[worker, None]),  # assignee found, master absent
    )
    _patch(monkeypatch, "claude_client.parse_deadline", return_value=deadline)

    with pytest.raises(WorkerNotRegisteredError):
        await task_service.create_task(
            AsyncMock(), MagicMock(), AsyncMock(), AsyncMock(),
            MASTER_TG_ID, WORKER_TG_ID, "task", "tomorrow", _make_config(),
        )


async def test_create_task_passes_timezone_to_deadline_parser(monkeypatch):
    """F5: parse_deadline must receive MASTER_TIMEZONE, not default UTC."""
    worker = _make_user(WORKER_TG_ID)
    master = _make_user(MASTER_TG_ID)
    task = _make_task()
    deadline = datetime.now(UTC) + timedelta(hours=2)

    monkeypatch.setattr(
        f"{_SVC}.users_repo.get_by_telegram_id",
        AsyncMock(side_effect=[worker, master]),
    )
    _patch(monkeypatch, "tasks_repo.create_task", return_value=task)
    monkeypatch.setattr(f"{_SVC}.schedule_task_jobs", MagicMock(return_value=("r1", "o1")))

    captured_tz: list[str] = []

    async def capture_parse(text: str, timezone: str = "UTC") -> datetime:
        captured_tz.append(timezone)
        return deadline

    monkeypatch.setattr(f"{_SVC}.claude_client.parse_deadline", capture_parse)

    cfg = _make_config()
    cfg.MASTER_TIMEZONE = "Europe/Kyiv"
    await task_service.create_task(
        AsyncMock(), MagicMock(), AsyncMock(), AsyncMock(),
        MASTER_TG_ID, WORKER_TG_ID, "report", "by 9am", cfg,
    )
    assert captured_tz == ["Europe/Kyiv"]
