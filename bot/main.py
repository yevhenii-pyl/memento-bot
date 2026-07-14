"""Bot entry point. Wires Dispatcher, registers routers, starts scheduler, runs polling."""
import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher

from bot.config import settings
from bot.shared.db import DbSessionMiddleware
from bot.shared.scheduler import create_scheduler


def build_dispatcher() -> Dispatcher:
    dp = Dispatcher()
    dp.update.middleware(DbSessionMiddleware())
    return dp


async def main() -> None:
    logging.basicConfig(level=settings.LOG_LEVEL, stream=sys.stdout)

    if not settings.BOT_TOKEN:
        logging.error("BOT_TOKEN is not set — exiting.")
        sys.exit(1)

    bot = Bot(token=settings.BOT_TOKEN)
    dp = build_dispatcher()

    scheduler = create_scheduler()
    scheduler.start()

    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
