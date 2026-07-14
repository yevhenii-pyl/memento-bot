"""Bot entry point. Wires Dispatcher, registers routers, starts scheduler, runs polling."""
import asyncio
import logging
import sys


def _load_settings():
    try:
        from bot.config import settings

        return settings
    except Exception as exc:
        print(
            "ERROR: Required environment variables are not set.\n"
            f"Details: {exc}\n"
            "Copy .env.example to .env and fill in the values.",
            file=sys.stderr,
        )
        sys.exit(1)


async def main() -> None:
    settings = _load_settings()

    logging.basicConfig(level=settings.LOG_LEVEL, stream=sys.stdout)

    from aiogram import Bot, Dispatcher

    from bot.shared.db import DbSessionMiddleware
    from bot.shared.scheduler import create_scheduler

    bot = Bot(token=settings.BOT_TOKEN)
    dp = Dispatcher()
    dp.update.middleware(DbSessionMiddleware())

    scheduler = create_scheduler()
    scheduler.start()

    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
