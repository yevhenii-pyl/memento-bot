"""Alembic env.py — imports all feature models so --autogenerate sees them."""
import os
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

# Load .env so DATABASE_URL is available outside Docker
load_dotenv()

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override sqlalchemy.url from environment if present
db_url = os.environ.get("DATABASE_URL", "")
if db_url:
    # Alembic uses the sync driver; strip +asyncpg if present
    config.set_main_option("sqlalchemy.url", db_url.replace("+asyncpg", ""))

# Import all feature model modules so their metadata is registered
# on Base before --autogenerate runs.  Add new model imports here.
from bot.shared.db import Base  # noqa: E402, F401
from bot.tasks.models import Task  # noqa: E402, F401
from bot.users.models import User  # noqa: E402, F401

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
