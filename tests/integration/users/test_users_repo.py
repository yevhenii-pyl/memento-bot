"""T02 integration tests — users repository."""
import uuid

import pytest

from bot.users import repo as users_repo
from bot.users.models import User


async def test_get_by_telegram_id_returns_user(async_session):
    user = User(id=uuid.uuid4(), telegram_id=10000001, display_name="Alice")
    async_session.add(user)
    await async_session.flush()

    result = await users_repo.get_by_telegram_id(async_session, 10000001)
    assert result is not None
    assert result.telegram_id == 10000001
    assert result.display_name == "Alice"


async def test_get_by_telegram_id_returns_none_for_unknown(async_session):
    result = await users_repo.get_by_telegram_id(async_session, 99999999)
    assert result is None


async def test_create_user_persists_row(async_session):
    user = await users_repo.create_user(async_session, telegram_id=20000001, display_name="Bob")
    assert user.id is not None
    assert user.telegram_id == 20000001
    assert user.display_name == "Bob"

    fetched = await users_repo.get_by_telegram_id(async_session, 20000001)
    assert fetched is not None
    assert fetched.id == user.id


async def test_create_user_unique_constraint(async_session):
    from sqlalchemy.exc import IntegrityError

    await users_repo.create_user(async_session, telegram_id=30000001, display_name="Charlie")
    with pytest.raises(IntegrityError):
        await users_repo.create_user(async_session, telegram_id=30000001, display_name="Duplicate")
