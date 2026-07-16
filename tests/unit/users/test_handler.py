"""T10 unit tests — users handler /start registration."""
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram.types import Message, User


def _make_message(user_id: int = 12345, display_name: str = "Alice") -> Message:
    msg = MagicMock(spec=Message)
    msg.from_user = MagicMock(spec=User)
    msg.from_user.id = user_id
    msg.from_user.full_name = display_name
    msg.answer = AsyncMock()
    return msg


async def test_start_handler_registers_and_replies():
    from bot.users.handler import handle_start

    msg = _make_message()
    session = AsyncMock()
    registered_user = MagicMock()
    registered_user.display_name = "Alice"

    with patch(
        "bot.users.handler.users_service.register_or_get",
        AsyncMock(return_value=registered_user),
    ):
        await handle_start(msg, session=session)

    msg.answer.assert_awaited_once()
    reply_text = msg.answer.call_args.args[0]
    assert "Alice" in reply_text or "registered" in reply_text.lower()


async def test_router_is_exported():
    from bot.users.handler import router

    assert router is not None
