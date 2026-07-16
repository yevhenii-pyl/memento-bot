---
status: Accepted
owner: "Architect / Tech Lead"
reviewers: ["Tech Lead"]
updated_at: "2026-07-15"
feature_size: "M"
ticket: "memento-task-core"
---

# 0005 — Model the task lifecycle as a status field with state-checked idempotency

- **Status:** Accepted
- **Date:** 2026-07-15
- **Deciders:** Architect + Product Owner (Socratic walk)

## Context

A task moves through a small lifecycle: created `open`, then `done` or `failed` at the Master's
verdict, or Extended — which logs the extension, sets a new future deadline, and returns to `open`
(spec AC-04…AC-06, AC-14). Outcome prompts are delivered via Telegram inline buttons that can be
tapped late or twice (stale message replay); the second tap must not change the recorded outcome
(spec AC-13, §6.1 abuse case). This is the feature's core domain invariant.

## Decision drivers

- Spec AC-13: idempotency is keyed on **task state**, not per message — a tap is ignored once the task is no longer awaiting an outcome for that deadline.
- Spec AC-06 / AC-14: Extend must record the extension, set a future (≥ 5 min) deadline, and re-open the task with fresh scheduled jobs (ADR-0001).
- Spec §7 KPI: failed-task rate must be queryable in the DB; the design should not foreclose the future stats feature.
- QG-2 (audit-trail integrity): the persisted verdict is always trustworthy.

## Considered options

1. **Single `status` field + state-checked idempotency** — `open`/`done`/`failed` on the task; the outcome callback acts only while the task still awaits an outcome for the prompt's deadline; a stale/duplicate tap is ignored with an "already recorded / no longer active" reply.
2. **Per-prompt token / optimistic version column** — each prompt carries a unique token; the callback is valid only for the current token.
3. **Event-sourced outcome log** — append-only outcome events; current status is derived.

## Decision outcome

**Chosen:** Option 1, **plus an `extension_count` column** on the task. A status field with a
state check satisfies AC-13's task-state keying directly and is the simplest thing that is correct:
the outcome callback re-reads the task and no-ops unless it is still awaiting an outcome for the
prompt's deadline. A per-prompt token adds bookkeeping for replay protection that state-keying
already covers; event sourcing is premature for v1. The `extension_count` column (incremented on
each Extend) is persisted for the future statistics feature but is **not** shown in v1 listings —
consistent with AC-07/AC-08, which state re-extended tasks appear identically to new open tasks.

## Consequences

**Positive**
- AC-13 idempotency falls out of a single re-read + status check — no extra tables or tokens.
- `resolved_at`, the extension timestamp, and `extension_count` give the audit trail spec §7 wants.
- The status field is a natural query key for the future stats feature (failed-task rate).

**Negative**
- The state check must be paired with the prompt's target deadline so a *newly re-opened* task (post-Extend) is not resolved by a stale prompt from the previous deadline — an explicit check in the callback handler (§8).
- Status is mutated in place, so there is no per-transition history beyond `extension_count` + `resolved_at`/extension timestamps (accepted for v1, §11).

**Neutral**
- `extension_count` display can be turned on later without a schema change.

## Links

- Spec: [[../spec.md]]
- SAD: [[../sad.md]] §4, §6, §8
- Related ADR: [[0001-schedule-durable-timers-via-apscheduler-postgres-job-store]]
