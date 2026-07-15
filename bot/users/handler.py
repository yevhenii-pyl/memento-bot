from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.users import service as users_service

router = Router()


@router.message(CommandStart())
async def handle_start(message: Message, session: AsyncSession) -> None:
    from_user = message.from_user
    if not from_user:
        return
    user = await users_service.register_or_get(
        session,
        telegram_id=from_user.id,
        display_name=from_user.full_name,
    )
    await message.answer(f"Welcome, {user.display_name}! You are now registered with Memento.")
