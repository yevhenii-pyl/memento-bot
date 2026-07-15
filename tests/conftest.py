"""Root test conftest — loads .env.test and routes DATABASE_URL to the test DB."""
import os

from dotenv import load_dotenv

load_dotenv(".env.test", override=False)

# Ensure Alembic (env.py) and async engines both point at the test database.
test_url = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://memento:memento@localhost:5432/memento_test",
)
os.environ.setdefault("TEST_DATABASE_URL", test_url)
os.environ["DATABASE_URL"] = test_url
