---
status: Accepted
owner: "Architect / Tech Lead"
reviewers: ["Tech Lead"]
updated_at: "2026-07-15"
feature_size: "M"
ticket: "memento-task-core"
---

# 0003 — Identify the Master by config and Workers by prior DM registration

- **Status:** Accepted
- **Date:** 2026-07-15
- **Deciders:** Architect + Product Owner (Socratic walk)

## Context

Only the Master may assign tasks to others and record outcomes; Workers may only self-commit
(spec §6.1, AC-10, AC-11). Tasks can be assigned only to people the bot can DM, and the bot must
never act on display names (impersonation, AC-12). The authorization check runs on every group
`/task` and on every outcome-prompt callback.

## Decision drivers

- Spec §6.1: the Master is identified by `MASTER_TELEGRAM_ID`; capture is confined to `MASTER_GROUP_CHAT_ID`; the bot acts on Telegram user IDs from `@mention` entities, never on display names.
- Spec §3 non-goal: multi-Master is out of scope — a single Master is a v1 architecture constraint.
- Spec AC-12: a "registered Worker" = any user who has previously initiated a private conversation with the bot.
- QG-2 (audit-trail integrity): every privileged action must be attributable to a verified identity.

## Considered options

1. **Config Master + DM-registered Workers** — Master = `MASTER_TELEGRAM_ID`; a Worker row is persisted on first `/start`; authz compares the caller's Telegram user ID against config / stored IDs.
2. **DB role table** — store `role` (master/worker) on a users table; the Master is a flagged row rather than a config value.

## Decision outcome

**Chosen:** Option 1. The single-Master constraint makes a config value the simplest correct
representation — there is exactly one privileged identity and it is operational config, not
user-managed data. Persisting Workers on `/start` gives a clean, spec-defined "registered"
predicate (AC-12) and a place to store the DM chat needed to reach them. A DB role table adds a
role-management surface that v1 explicitly does not want.

## Consequences

**Positive**
- Authz is a cheap equality check against config / a stored user ID on every privileged action.
- "Registered Worker" is a concrete, testable predicate (a users row exists).
- Acting only on Telegram user IDs closes the display-name impersonation abuse case.

**Negative**
- Changing the Master means changing config and restarting — acceptable under the single-Master constraint.
- Multi-Master would require replacing the config check with a DB role model (noted in §11).

**Neutral**
- The users table also holds each Worker's private chat reference, reused by the reminder/notification flow.

## Links

- Spec: [[../spec.md]]
- SAD: [[../sad.md]] §4, §8
- Related ADR: [[0005-model-task-lifecycle-as-a-status-field-with-state-checked-idempotency]]
