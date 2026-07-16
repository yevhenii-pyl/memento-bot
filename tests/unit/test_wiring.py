"""T14 unit tests — bot entry point wiring."""
import importlib


def test_users_router_exported():
    from bot.users.handler import router

    assert router is not None


def test_tasks_router_exported():
    from bot.tasks.handler import router

    assert router is not None


def test_main_py_includes_both_routers():
    """Ensure main.py source references both handler routers."""
    main_src = open("bot/main.py").read()
    assert "users_handler" in main_src or "users.handler" in main_src, (
        "main.py must include users handler router"
    )
    assert "tasks_handler" in main_src or "tasks.handler" in main_src, (
        "main.py must include tasks handler router"
    )


def test_env_example_documents_all_required_vars():
    required = {
        "BOT_TOKEN",
        "DATABASE_URL",
        "ANTHROPIC_API_KEY",
        "MASTER_TELEGRAM_ID",
        "MASTER_GROUP_CHAT_ID",
        "MASTER_TIMEZONE",
    }
    content = open(".env.example").read()
    keys_in_file = {line.split("=")[0] for line in content.splitlines() if "=" in line}
    missing = required - keys_in_file
    assert not missing, f".env.example is missing required vars: {missing}"


def test_config_has_master_settings(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "x")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://h/db")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setenv("MASTER_TELEGRAM_ID", "12345")
    monkeypatch.setenv("MASTER_GROUP_CHAT_ID", "-99999")
    monkeypatch.setenv("MASTER_TIMEZONE", "Europe/London")

    import bot.config as cfg_mod

    importlib.reload(cfg_mod)
    cfg = cfg_mod.settings
    assert cfg.MASTER_TELEGRAM_ID == 12345
    assert cfg.MASTER_GROUP_CHAT_ID == -99999
    assert cfg.MASTER_TIMEZONE == "Europe/London"
    importlib.reload(cfg_mod)
