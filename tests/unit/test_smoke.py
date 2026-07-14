"""Smoke tests: verify config loads and critical settings are present."""
import pytest


@pytest.fixture(autouse=True)
def set_required_env(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "smoke_test_token")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://memento:memento@localhost:5432/memento")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "smoke_test_key")
    import importlib

    import bot.config as cfg_mod

    importlib.reload(cfg_mod)
    yield
    importlib.reload(cfg_mod)


def test_config_loads():
    import bot.config as cfg_mod

    cfg = cfg_mod.settings
    assert cfg.BOT_TOKEN, "BOT_TOKEN must be set"


def test_database_url_present():
    import bot.config as cfg_mod

    cfg = cfg_mod.settings
    assert cfg.DATABASE_URL.startswith("postgresql"), (
        f"DATABASE_URL must be a PostgreSQL URL, got: {cfg.DATABASE_URL}"
    )


def test_anthropic_key_present():
    import bot.config as cfg_mod

    cfg = cfg_mod.settings
    assert cfg.ANTHROPIC_API_KEY, "ANTHROPIC_API_KEY must be set"


def test_module_structure():
    """All required feature packages must be importable."""
    import importlib

    for mod in [
        "bot.tasks",
        "bot.users",
        "bot.notifications",
        "bot.stats",
        "bot.shared",
        "bot.shared.db",
        "bot.shared.exceptions",
        "bot.shared.claude_client",
        "bot.shared.scheduler",
    ]:
        assert importlib.import_module(mod) is not None, f"Cannot import {mod}"
