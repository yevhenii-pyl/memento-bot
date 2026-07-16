"""T09 unit tests — task service outcome recording and idempotency."""
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from bot.shared.exceptions import (
    DeadlineParseError,
    DeadlineTooSoonError,
    OutcomeAlreadyRecordedError,
)
from bot.tasks import service as task_service

_SVC = "bot.tasks.service"
TASK_ID = uuid.uuid4()


def _make_task(status: str = "pending") -> MagicMock:
    t = MagicMock()
    t.id = TASK_ID
    t.status = status
    t.deadline = datetime.now(UTC) + timedelta(hours=2)
    t.title = "Test task"
    t.assignee_id = uuid.uuid4()
    return t


def _patch(mp, attr, **kw):
    mp.setattr(f"{_SVC}.{attr}", AsyncMock(**kw))


async def test_record_done_transitions_status(monkeypatch):
    task = _make_task(status="pending")
    _patch(monkeypatch, "tasks_repo.get_by_id", return_value=task)
    _patch(monkeypatch, "tasks_repo.update_status")
    monkeypatch.setattr(f"{_SVC}.cancel_task_jobs", MagicMock())

    result = await task_service.record_done(
        AsyncMock(), MagicMock(), TASK_ID, "r1", "o1"
    )
    assert result is task
    task_service.cancel_task_jobs.assert_called_once()


async def test_record_done_raises_on_non_pending(monkeypatch):
    task = _make_task(status="done")
    _patch(monkeypatch, "tasks_repo.get_by_id", return_value=task)

    with pytest.raises(OutcomeAlreadyRecordedError):
        await task_service.record_done(AsyncMock(), MagicMock(), TASK_ID, "r1", "o1")


async def test_record_failed_transitions_status(monkeypatch):
    task = _make_task(status="pending")
    _patch(monkeypatch, "tasks_repo.get_by_id", return_value=task)
    _patch(monkeypatch, "tasks_repo.update_status")
    monkeypatch.setattr(f"{_SVC}.cancel_task_jobs", MagicMock())

    result = await task_service.record_failed(
        AsyncMock(), MagicMock(), TASK_ID, "r1", "o1"
    )
    assert result is task


async def test_record_failed_raises_on_non_pending(monkeypatch):
    task = _make_task(status="failed")
    _patch(monkeypatch, "tasks_repo.get_by_id", return_value=task)

    with pytest.raises(OutcomeAlreadyRecordedError):
        await task_service.record_failed(AsyncMock(), MagicMock(), TASK_ID, "r1", "o1")


async def test_record_extended_valid_deadline(monkeypatch):
    task = _make_task(status="pending")
    new_deadline = datetime.now(UTC) + timedelta(hours=3)
    _patch(monkeypatch, "tasks_repo.get_by_id", return_value=task)
    _patch(monkeypatch, "claude_client.parse_deadline", return_value=new_deadline)
    _patch(monkeypatch, "tasks_repo.record_extension")
    monkeypatch.setattr(
        f"{_SVC}.reschedule_task_jobs", MagicMock(return_value=("r2", "o2"))
    )

    cfg = MagicMock()
    cfg.MASTER_TIMEZONE = "UTC"
    result = await task_service.record_extended(
        AsyncMock(), MagicMock(), AsyncMock(), AsyncMock(),
        TASK_ID, "in 3 hours", cfg, "r1", "o1",
    )
    assert result is task
    task_service.reschedule_task_jobs.assert_called_once()


async def test_record_extended_deadline_too_soon(monkeypatch):
    task = _make_task(status="pending")
    soon = datetime.now(UTC) + timedelta(minutes=2)
    _patch(monkeypatch, "tasks_repo.get_by_id", return_value=task)
    _patch(monkeypatch, "claude_client.parse_deadline", return_value=soon)

    cfg = MagicMock()
    cfg.MASTER_TIMEZONE = "UTC"
    with pytest.raises(DeadlineTooSoonError):
        await task_service.record_extended(
            AsyncMock(), MagicMock(), AsyncMock(), AsyncMock(),
            TASK_ID, "in 2 minutes", cfg, "r1", "o1",
        )


async def test_record_extended_unresolvable_deadline(monkeypatch):
    task = _make_task(status="pending")
    _patch(monkeypatch, "tasks_repo.get_by_id", return_value=task)
    _patch(monkeypatch, "claude_client.parse_deadline", return_value=None)

    cfg = MagicMock()
    cfg.MASTER_TIMEZONE = "UTC"
    with pytest.raises(DeadlineParseError):
        await task_service.record_extended(
            AsyncMock(), MagicMock(), AsyncMock(), AsyncMock(),
            TASK_ID, "gibberish", cfg, "r1", "o1",
        )


async def test_record_done_status_unchanged_on_second_tap(monkeypatch):
    """AC-13: after Done, a second tap must not mutate status or call update_status again."""
    pending = _make_task(status="pending")
    done = _make_task(status="done")

    get_mock = AsyncMock(side_effect=[pending, done])
    monkeypatch.setattr(f"{_SVC}.tasks_repo.get_by_id", get_mock)
    update_mock = AsyncMock()
    monkeypatch.setattr(f"{_SVC}.tasks_repo.update_status", update_mock)
    monkeypatch.setattr(f"{_SVC}.cancel_task_jobs", MagicMock())

    await task_service.record_done(AsyncMock(), MagicMock(), TASK_ID, "r1", "o1")

    import pytest as _pytest
    with _pytest.raises(OutcomeAlreadyRecordedError):
        await task_service.record_done(AsyncMock(), MagicMock(), TASK_ID, "r1", "o1")

    assert update_mock.await_count == 1, "update_status must only be called once"


async def test_record_extended_raises_on_non_pending(monkeypatch):
    task = _make_task(status="done")
    _patch(monkeypatch, "tasks_repo.get_by_id", return_value=task)

    cfg = MagicMock()
    with pytest.raises(OutcomeAlreadyRecordedError):
        await task_service.record_extended(
            AsyncMock(), MagicMock(), AsyncMock(), AsyncMock(),
            TASK_ID, "tomorrow", cfg, "r1", "o1",
        )
