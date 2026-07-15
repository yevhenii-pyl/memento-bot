"""T03 integration tests — tasks repository."""
import uuid
from datetime import UTC, datetime, timedelta

from bot.tasks import repo as tasks_repo
from bot.users.models import User


async def _make_users(session):
    worker = User(id=uuid.uuid4(), telegram_id=40000001, display_name="Worker")
    master = User(id=uuid.uuid4(), telegram_id=40000002, display_name="Master")
    session.add_all([worker, master])
    await session.flush()
    return worker, master


async def _deadline(offset_hours: int = 24) -> datetime:
    return datetime.now(UTC) + timedelta(hours=offset_hours)


async def test_create_task(async_session):
    worker, master = await _make_users(async_session)
    deadline = await _deadline()

    task = await tasks_repo.create_task(
        async_session,
        assignee_id=worker.id,
        overseer_id=master.id,
        title="Deliver report",
        deadline=deadline,
    )

    assert task.id is not None
    assert task.assignee_id == worker.id
    assert task.overseer_id == master.id
    assert task.title == "Deliver report"
    assert task.status == "open"
    assert task.extension_count == 0
    assert task.resolved_at is None


async def test_set_pending(async_session):
    worker, master = await _make_users(async_session)
    task = await tasks_repo.create_task(
        async_session, worker.id, master.id, "Task", await _deadline()
    )
    await tasks_repo.set_pending(async_session, task.id)
    await async_session.refresh(task)
    assert task.status == "pending"


async def test_update_status_done(async_session):
    worker, master = await _make_users(async_session)
    task = await tasks_repo.create_task(
        async_session, worker.id, master.id, "Task", await _deadline()
    )
    await tasks_repo.update_status(async_session, task.id, "done")
    await async_session.refresh(task)
    assert task.status == "done"
    assert task.resolved_at is not None


async def test_update_status_failed(async_session):
    worker, master = await _make_users(async_session)
    task = await tasks_repo.create_task(
        async_session, worker.id, master.id, "Task", await _deadline()
    )
    await tasks_repo.update_status(async_session, task.id, "failed")
    await async_session.refresh(task)
    assert task.status == "failed"
    assert task.resolved_at is not None


async def test_record_extension(async_session):
    worker, master = await _make_users(async_session)
    task = await tasks_repo.create_task(
        async_session, worker.id, master.id, "Task", await _deadline()
    )
    new_deadline = await _deadline(offset_hours=48)
    await tasks_repo.record_extension(async_session, task.id, new_deadline)
    await async_session.refresh(task)
    assert task.status == "open"
    assert task.extension_count == 1
    assert task.extension_timestamp is not None
    assert abs((task.deadline - new_deadline).total_seconds()) < 1


async def test_get_open_by_assignee(async_session):
    worker, master = await _make_users(async_session)
    task1 = await tasks_repo.create_task(
        async_session, worker.id, master.id, "Open task", await _deadline()
    )
    task2 = await tasks_repo.create_task(
        async_session, worker.id, master.id, "Another open", await _deadline(48)
    )
    # Create a done task that should NOT appear
    task3 = await tasks_repo.create_task(
        async_session, worker.id, master.id, "Done task", await _deadline()
    )
    await tasks_repo.update_status(async_session, task3.id, "done")

    open_tasks = await tasks_repo.get_open_by_assignee(async_session, worker.id)
    open_ids = {t.id for t in open_tasks}
    assert task1.id in open_ids
    assert task2.id in open_ids
    assert task3.id not in open_ids


async def test_get_task_by_id(async_session):
    worker, master = await _make_users(async_session)
    task = await tasks_repo.create_task(
        async_session, worker.id, master.id, "Find me", await _deadline()
    )
    found = await tasks_repo.get_by_id(async_session, task.id)
    assert found is not None
    assert found.id == task.id

    not_found = await tasks_repo.get_by_id(async_session, uuid.uuid4())
    assert not_found is None
