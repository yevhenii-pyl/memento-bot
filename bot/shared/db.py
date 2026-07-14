from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from bot.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False)
async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine, expire_on_commit=False
)


class Base(DeclarativeBase):
    pass


class DbSessionMiddleware:
    """aiogram middleware that injects an AsyncSession into handler data."""

    async def __call__(self, handler, event, data):
        async with async_session_factory() as session:
            data["session"] = session
            return await handler(event, data)
