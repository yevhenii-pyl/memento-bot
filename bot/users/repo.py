import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.users.models import User


async def get_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    return result.scalar_one_or_none()


async def create_user(session: AsyncSession, telegram_id: int, display_name: str) -> User:
    user = User(id=uuid.uuid4(), telegram_id=telegram_id, display_name=display_name)
    session.add(user)
    await session.flush()
    return user
