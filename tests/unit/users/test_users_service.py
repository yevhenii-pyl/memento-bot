"""T04 unit tests — users service (register_or_get idempotency)."""
import uuid
from unittest.mock import AsyncMock

from bot.users import service as users_service
from bot.users.models import User


def _make_session():
    return AsyncMock()


def _make_user(telegram_id: int = 123456, display_name: str = "Alice") -> User:
    return User(id=uuid.uuid4(), telegram_id=telegram_id, display_name=display_name)


async def test_register_or_get_returns_existing_user(monkeypatch):
    existing = _make_user()
    session = _make_session()

    monkeypatch.setattr(
        "bot.users.service.users_repo.get_by_telegram_id",
        AsyncMock(return_value=existing),
    )
    monkeypatch.setattr(
        "bot.users.service.users_repo.create_user",
        AsyncMock(),
    )

    result = await users_service.register_or_get(session, telegram_id=123456, display_name="Alice")
    assert result is existing
    users_service.users_repo.create_user.assert_not_called()


async def test_register_or_get_creates_new_user(monkeypatch):
    new_user = _make_user(telegram_id=999999)
    session = _make_session()

    monkeypatch.setattr(
        "bot.users.service.users_repo.get_by_telegram_id",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "bot.users.service.users_repo.create_user",
        AsyncMock(return_value=new_user),
    )

    result = await users_service.register_or_get(session, telegram_id=999999, display_name="Bob")
    assert result is new_user
    users_service.users_repo.create_user.assert_called_once_with(
        session, telegram_id=999999, display_name="Bob"
    )


async def test_all_domain_exceptions_defined():
    from bot.shared.exceptions import (
        DeadlineParseError,
        DeadlineTooSoonError,
        MementoError,
        OutcomeAlreadyRecordedError,
        TaskNotFoundError,
        UnauthorizedError,
        UserNotFoundError,
        WorkerNotRegisteredError,
    )

    assert issubclass(DeadlineParseError, MementoError)
    assert issubclass(DeadlineTooSoonError, MementoError)
    assert issubclass(OutcomeAlreadyRecordedError, MementoError)
    assert issubclass(TaskNotFoundError, MementoError)
    assert issubclass(UnauthorizedError, MementoError)
    assert issubclass(UserNotFoundError, MementoError)
    assert issubclass(WorkerNotRegisteredError, MementoError)
