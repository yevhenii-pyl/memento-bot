---
status: Accepted
owner: "Architect / Tech Lead"
reviewers: ["Tech Lead"]
updated_at: "2026-07-15"
feature_size: "M"
ticket: "memento-task-core"
---

# 0001 — Schedule durable per-task timers via APScheduler with a PostgreSQL job store

- **Status:** Accepted
- **Date:** 2026-07-15
- **Deciders:** Architect + Product Owner (Socratic walk)

## Context

Every task needs two future actions: a reminder to the Worker 5 minutes before the deadline
and an outcome prompt to the Master at the deadline. The bot is a single long-running process
(§4, §5) that can restart (deploy, crash) between a task's creation and its deadline. Spec §6
requires **zero scheduled jobs lost across restarts** and reminder/outcome drift **≤ 60 s**.

## Decision drivers

- Spec §6 NFR: "Scheduler job durability — zero jobs lost across bot restarts" (verified by an integration test: schedule → restart → confirm fire).
- Spec §6 NFR: reminder drift ≤ 60 s and outcome-prompt drift ≤ 60 s from the scheduled time.
- §2 constraint: single bot instance, no horizontal scaling in v1; PostgreSQL 16 already in the stack.
- QG-1 (notification timing reliability) is the product's core value.

## Considered options

1. **APScheduler `AsyncIOScheduler` + PostgreSQL job store** — timers run in-process; jobs persist in Postgres and reload on startup.
2. **DB-persisted next-fire times + a periodic sweep** — store fire times on the task; a reconciler polls for due rows and fires.
3. **External scheduler service** — delegate timers to a dedicated cron/queue component.

## Decision outcome

**Chosen:** Option 1. The PostgreSQL job store gives restart durability for free — pending jobs
reload on startup — with no extra moving parts, since Postgres is already the datastore. Precise
per-job firing meets the ≤ 60 s drift target directly, whereas a sweep's granularity is bounded by
its poll interval. An external scheduler is over-engineered for a single-instance v1.

## Consequences

**Positive**
- Restart-safety satisfied by the job store; the durability NFR is testable end-to-end.
- Per-job firing keeps drift well under 60 s.
- No new infrastructure — reuses PostgreSQL and the in-process event loop.

**Negative**
- Timers are coupled to the single process; horizontal scaling later requires an external/distributed job store (noted in §11).
- Job-store rows and domain rows can drift if a task is deleted without unscheduling its jobs — mitigated by unscheduling in the same service call (§8).

**Neutral**
- On Extend, both jobs are rescheduled for the new deadline rather than mutated in place (ADR-0005).

## Links

- Spec: [[../spec.md]]
- SAD: [[../sad.md]] §4, §5, §7
- Related ADR: [[0005-model-task-lifecycle-as-a-status-field-with-state-checked-idempotency]]
