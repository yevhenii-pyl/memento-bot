from sqlalchemy.ext.asyncio import AsyncSession

from bot.users import repo as users_repo
from bot.users.models import User


async def register_or_get(session: AsyncSession, telegram_id: int, display_name: str) -> User:
    user = await users_repo.get_by_telegram_id(session, telegram_id)
    if user is None:
        user = await users_repo.create_user(
            session, telegram_id=telegram_id, display_name=display_name
        )
    else:
        user = await users_repo.update_display_name(session, user, display_name)
    return user
