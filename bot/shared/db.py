from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


_engine = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine():
    global _engine
    if _engine is None:
        from bot.config import settings

        _engine = create_async_engine(settings.DATABASE_URL, echo=False)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _async_session_factory
    if _async_session_factory is None:
        _async_session_factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _async_session_factory


class DbSessionMiddleware:
    """aiogram middleware that injects an AsyncSession into handler data."""

    async def __call__(self, handler, event, data):
        async with get_session_factory()() as session:
            data["session"] = session
            return await handler(event, data)
