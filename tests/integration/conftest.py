"""Integration test fixtures — provides a real async DB session via Alembic."""
import os

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://memento:memento@localhost:5432/memento_test",
)
_SYNC_URL = TEST_DATABASE_URL.replace("+asyncpg", "")


@pytest.fixture(scope="session")
def run_migrations():
    """Apply migrations once per session; downgrade when the session ends."""
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", _SYNC_URL)
    command.upgrade(alembic_cfg, "head")
    yield
    command.downgrade(alembic_cfg, "base")


@pytest_asyncio.fixture
async def async_session(run_migrations) -> AsyncSession:
    """Per-test session wrapped in a rolled-back transaction for isolation."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.connect() as conn:
        await conn.begin()
        session = AsyncSession(conn, expire_on_commit=False)
        try:
            yield session
        finally:
            await session.close()
            await conn.rollback()
    await engine.dispose()
