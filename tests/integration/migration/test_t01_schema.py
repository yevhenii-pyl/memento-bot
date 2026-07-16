"""T01 integration tests — ORM models, migrations, async_session fixture."""
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError

from bot.tasks.models import Task
from bot.users.models import User


async def test_async_session_fixture_works(async_session):
    assert async_session is not None


async def test_user_model_insert(async_session):
    user = User(id=uuid.uuid4(), telegram_id=123456789, display_name="Test User")
    async_session.add(user)
    await async_session.flush()
    await async_session.refresh(user)

    assert user.id is not None
    assert user.telegram_id == 123456789
    assert user.display_name == "Test User"
    assert user.created_at is not None
    assert user.updated_at is not None


async def test_task_model_insert(async_session):
    assignee = User(id=uuid.uuid4(), telegram_id=111111111, display_name="Worker")
    overseer = User(id=uuid.uuid4(), telegram_id=222222222, display_name="Master")
    async_session.add_all([assignee, overseer])
    await async_session.flush()

    deadline = datetime(2026, 12, 31, 12, 0, 0, tzinfo=UTC)
    task = Task(
        id=uuid.uuid4(),
        assignee_id=assignee.id,
        overseer_id=overseer.id,
        title="Test commitment",
        deadline=deadline,
        status="open",
    )
    async_session.add(task)
    await async_session.flush()
    await async_session.refresh(task)

    assert task.id is not None
    assert task.title == "Test commitment"
    assert task.status == "open"
    assert task.extension_count == 0
    assert task.resolved_at is None
    assert task.extension_timestamp is None


async def test_unique_telegram_id_enforced(async_session):
    tg_id = 999888777
    user1 = User(id=uuid.uuid4(), telegram_id=tg_id, display_name="First")
    async_session.add(user1)
    await async_session.flush()

    user2 = User(id=uuid.uuid4(), telegram_id=tg_id, display_name="Duplicate")
    async_session.add(user2)
    with pytest.raises(IntegrityError):
        await async_session.flush()
