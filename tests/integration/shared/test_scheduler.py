"""T07 integration tests — APScheduler schedule/cancel/restart durability."""
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

from bot.shared.scheduler import cancel_task_jobs, create_scheduler, schedule_task_jobs


class _FakeBot:
    """Picklable bot stub — actual sends are never called in these tests."""

    async def send_message(self, **kwargs):
        pass


@asynccontextmanager
async def _fake_session():
    yield MagicMock()


def _fake_session_factory():
    return _fake_session()


def _make_task(deadline: datetime) -> MagicMock:
    task = MagicMock()
    task.id = uuid.uuid4()
    task.deadline = deadline
    return task


async def test_schedule_creates_two_jobs():
    scheduler = create_scheduler()
    scheduler.start()
    try:
        task = _make_task(datetime.now(UTC) + timedelta(hours=2))
        reminder_id, outcome_id = schedule_task_jobs(
            scheduler, _FakeBot(), _fake_session_factory, task
        )
        assert reminder_id is not None
        assert outcome_id is not None
        assert scheduler.get_job(reminder_id) is not None
        assert scheduler.get_job(outcome_id) is not None
    finally:
        scheduler.shutdown(wait=False)


async def test_cancel_removes_jobs():
    scheduler = create_scheduler()
    scheduler.start()
    try:
        task = _make_task(datetime.now(UTC) + timedelta(hours=2))
        reminder_id, outcome_id = schedule_task_jobs(
            scheduler, _FakeBot(), _fake_session_factory, task
        )
        cancel_task_jobs(scheduler, reminder_id, outcome_id)
        assert scheduler.get_job(reminder_id) is None
        assert scheduler.get_job(outcome_id) is None
    finally:
        scheduler.shutdown(wait=False)


async def test_cancel_tolerates_missing_jobs():
    scheduler = create_scheduler()
    scheduler.start()
    try:
        cancel_task_jobs(scheduler, "nonexistent-1", "nonexistent-2")
    finally:
        scheduler.shutdown(wait=False)


async def test_scheduler_restart_durability():
    """Jobs persisted to the job store survive a scheduler restart (QG-1)."""
    task = _make_task(datetime.now(UTC) + timedelta(hours=3))
    scheduler1 = create_scheduler()
    scheduler1.start()
    try:
        reminder_id, outcome_id = schedule_task_jobs(
            scheduler1, _FakeBot(), _fake_session_factory, task
        )
    finally:
        scheduler1.shutdown(wait=False)

    # Re-instantiate pointing at the same job store — jobs must survive
    scheduler2 = create_scheduler()
    scheduler2.start()
    try:
        assert scheduler2.get_job(reminder_id) is not None, "Reminder job lost across restart"
        assert scheduler2.get_job(outcome_id) is not None, "Outcome job lost across restart"
    finally:
        cancel_task_jobs(scheduler2, reminder_id, outcome_id)
        scheduler2.shutdown(wait=False)


async def test_immediate_reminder_when_deadline_under_5min():
    """Reminder fires ~1 second from now if deadline is < 5 min away (AC-03)."""
    now = datetime.now(UTC)
    task = _make_task(now + timedelta(minutes=2))
    scheduler = create_scheduler()
    scheduler.start()
    try:
        reminder_id, outcome_id = schedule_task_jobs(
            scheduler, _FakeBot(), _fake_session_factory, task
        )
        reminder_job = scheduler.get_job(reminder_id)
        assert reminder_job is not None
        fire_time = reminder_job.next_run_time
        assert fire_time is not None
        delta = (fire_time - now).total_seconds()
        assert delta < 5, f"Expected immediate reminder, got {delta:.1f}s delay"
    finally:
        scheduler.shutdown(wait=False)
