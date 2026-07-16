# Changelog — memento-task-core

## memento-task-core — Accountability loop: task capture, reminder, and outcome verdict

**What:** The bot can now capture verbal commitments made in the team's group chat (`MASTER_GROUP_CHAT_ID`) as tracked tasks with deadlines. The Worker receives a private reminder 5 minutes before the deadline. At deadline, the Master receives a private outcome prompt and records Done, Failed, or Extended. Extended tasks re-enter the full cycle with a new deadline. Workers can list their open tasks; the Master can list any Worker's open tasks.

**Why:** Verbal commitments in Telegram were being forgotten with no accountability loop — no reminder to the Worker, no structured prompt to the Master to check delivery. See [spec §1–§2](./spec.md). Key decisions:

- [ADR-0001](./adr/0001-schedule-durable-timers-via-apscheduler-postgres-job-store.md) — Durable job scheduling via APScheduler + PostgreSQL job store (survives restarts).
- [ADR-0002](./adr/0002-parse-deadlines-synchronously-in-the-creation-flow.md) — Deadline parsing via Claude API call inline at task creation (no async queue).
- [ADR-0003](./adr/0003-identify-master-by-config-and-workers-by-prior-dm-registration.md) — Master identified by `MASTER_TELEGRAM_ID`; Workers by prior `/start` DM (no invite flow).
- [ADR-0004](./adr/0004-store-timestamps-as-utc-and-anchor-relative-deadlines-to-master-timezone.md) — All timestamps UTC in DB; relative deadlines anchored to `MASTER_TIMEZONE` at parse time.
- [ADR-0005](./adr/0005-model-task-lifecycle-as-a-status-field-with-state-checked-idempotency.md) — Task lifecycle as a `status` enum column with state-checked idempotency on outcome taps.

**How to use:**

1. In the group chat, Master assigns: `/task @Worker Fix the login bug by EOD`
2. In the group chat, Worker self-commits: `/task Send the mockups by 5pm`
3. Worker receives private reminder 5 min before deadline; Master receives outcome prompt at deadline.
4. Master taps Done / Failed / Extended. Extended prompts for a new deadline; the cycle restarts.
5. List open tasks: Worker DMs `/tasks` to the bot. Master DMs `/tasks @Worker` to list a specific Worker's tasks.

**Operational notes:**

- Migration: adds **3 Alembic migrations** (`0001_initial_schema`, `0002_create_users`, `0003_create_tasks`). Run `alembic upgrade head` before starting the bot. Rollback: `alembic downgrade -3` + revert the deploy.
- Config: requires `BOT_TOKEN`, `DATABASE_URL` (PostgreSQL), `ANTHROPIC_API_KEY`, `MASTER_TELEGRAM_ID`, `MASTER_GROUP_CHAT_ID`, `MASTER_TIMEZONE` (IANA string, e.g. `Europe/Kyiv`). See `.env.example`.
- APScheduler uses `SQLAlchemyJobStore` pointing at the same `DATABASE_URL`; no separate scheduler DB needed.
- Feature flag: none.

**Acceptance criteria delivered:** AC-01, AC-02, AC-03, AC-04, AC-05, AC-06, AC-07, AC-08, AC-09, AC-10, AC-11, AC-12, AC-13, AC-14.
