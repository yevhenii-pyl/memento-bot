---
status: Accepted
owner: "Architect / Tech Lead"
reviewers: ["Tech Lead"]
updated_at: "2026-07-15"
feature_size: "M"
ticket: "memento-task-core"
---

# 0004 — Store timestamps as UTC and anchor relative deadlines to MASTER_TIMEZONE

- **Status:** Accepted
- **Date:** 2026-07-15
- **Deciders:** Architect + Product Owner (Socratic walk)

## Context

Deadlines arrive as relative phrases ("by EOD", "in 2 hours") and every user-facing time — group
confirmation, reminder, outcome prompt, task listing — must be shown in the team's timezone
(spec AC-01…AC-09). The whole team shares a single `MASTER_TIMEZONE` (IANA string); per-user
timezones are a spec non-goal. Deadlines drive durable scheduled jobs (ADR-0001), so their stored
representation must be unambiguous across restarts and DST transitions.

## Decision drivers

- Spec AC-09: relative deadlines are resolved against `MASTER_TIMEZONE` at the time the message is received.
- Spec §3 non-goal: per-user / per-task timezone overrides are out of scope; one team `MASTER_TIMEZONE`.
- Spec §6 NFR: scheduling drift ≤ 60 s — the stored instant must be exact and DST-safe.
- QG-2 (audit-trail integrity): a persisted deadline must mean one unambiguous instant.

## Considered options

1. **UTC (timezone-aware) storage + MASTER_TIMEZONE for all I/O** — resolve relative phrases against `MASTER_TIMEZONE` at receipt, store the resulting instant as tz-aware UTC, format output back into `MASTER_TIMEZONE`.
2. **Naive local-time storage** — store deadlines as naive datetimes already in the team's local time.

## Decision outcome

**Chosen:** Option 1. Storing tz-aware UTC gives every deadline one unambiguous instant that is
stable across restarts and DST, which the durable scheduler (ADR-0001) depends on. Timezone is a
pure presentation/parse concern anchored to one config value. Naive local storage couples the
persisted audit trail to a mutable config and invites DST/ambiguity bugs.

## Consequences

**Positive**
- One canonical instant per deadline — safe for scheduling, comparison, and the audit trail.
- DST transitions handled at the edges (parse + format), not in storage.
- Changing `MASTER_TIMEZONE` display later does not corrupt stored data.

**Negative**
- Every user-facing time needs an explicit UTC → `MASTER_TIMEZONE` conversion; forgetting one shows the wrong time (mitigated by a single shared formatting helper, §8).

**Neutral**
- Introducing per-user timezones later means adding a per-user offset at the presentation layer only — storage stays UTC.

## Links

- Spec: [[../spec.md]]
- SAD: [[../sad.md]] §4, §8
- Related ADR: [[0002-parse-deadlines-synchronously-in-the-creation-flow]]
