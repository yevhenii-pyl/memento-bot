from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot.config import settings


def create_scheduler() -> AsyncIOScheduler:
    jobstores = {
        "default": SQLAlchemyJobStore(url=settings.DATABASE_URL.replace("+asyncpg", ""))
    }
    return AsyncIOScheduler(jobstores=jobstores)
