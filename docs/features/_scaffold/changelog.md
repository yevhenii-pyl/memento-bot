# Changelog — _scaffold

## _scaffold — Greenfield project skeleton for Memento bot

**What:** Establishes the complete project skeleton for the Memento Telegram bot — Python package, feature-based module structure, test harness, Alembic migration baseline, GitHub Actions CI, CLAUDE.md conventions, and Docker/Compose dev environment.

**Why:** Before any domain feature (tasks, users, notifications) can be built, the project needs a reproducible foundation: a correct package layout, a working DB connection pattern, a test runner, and CI that enforces quality on every PR. See [ADR-0001](../../adr/0001-python-aiogram-stack.md) (stack choice: Python + aiogram), [ADR-0002](../../adr/0002-feature-based-module-structure.md) (module boundaries), [ADR-0003](../../adr/0003-postgresql-sqlalchemy-alembic.md) (DB + migration tooling).

**How to use:**
```bash
cp .env.example .env        # fill in BOT_TOKEN, DATABASE_URL, ANTHROPIC_API_KEY
pip install -e .[dev]
alembic upgrade head
python -m bot.main
```
Or with Docker Compose (requires `.env` to exist first):
```bash
docker compose up
docker compose run bot alembic upgrade head
```

**Operational notes:**
- Migration: adds `migrations/versions/0001_initial_schema.py` — an empty baseline. Apply with `alembic upgrade head`; revert with `alembic downgrade base`.
- Feature flag / config: none.
- Rollback: drop the DB / delete the migration file and revert the deploy. No data at risk — schema is empty.

**Acceptance criteria delivered:** Scaffold has no domain ACs. All S1–S6 DoDs are satisfied (see `tracker.md`).
