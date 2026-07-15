---
status: Accepted
owner: "Architect / Tech Lead"
reviewers: ["Tech Lead"]
updated_at: "2026-07-15"
feature_size: "M"
ticket: "memento-task-core"
---

# 0002 — Parse deadlines synchronously in the task-creation flow

- **Status:** Accepted
- **Date:** 2026-07-15
- **Deciders:** Architect + Product Owner (Socratic walk)

## Context

`/task` bodies carry natural-language deadlines ("by EOD", "tomorrow 9am") that must be resolved
to a concrete datetime before a task can be created (spec AC-01, AC-09). Resolution goes through
the Claude API (`bot/shared/claude_client.py`). The parse sits on the interactive creation path,
so its latency is visible to the user in the group chat.

## Decision drivers

- Spec §6 NFR: task-creation latency p95 ≤ 5 s end-to-end **including deadline parsing**.
- Spec AC-09: an unparseable or past deadline must be rejected with an inline "please rephrase" reply and **no task created** — i.e. the outcome must be known before the handler replies.
- §2 convention: all Claude calls go through `bot/shared/claude_client.py`.

## Considered options

1. **Synchronous inline parse** — call Claude during `/task` handling; on success create the task, on failure reject inline.
2. **Async background parse + follow-up message** — acknowledge immediately, parse in the background, post the confirmation/rejection later.

## Decision outcome

**Chosen:** Option 1. A synchronous parse lets the handler decide create-or-reject in one turn,
which is exactly what AC-09 requires, and keeps the implementation simple. The p95 ≤ 5 s budget
comfortably accommodates a single Claude call. The async path's two-phase UX and pending-parse
state buy nothing until Claude latency actually threatens the budget.

## Consequences

**Positive**
- AC-09's create-or-reject decision is made in a single handler turn — clean UX, simple code.
- No pending-parse state to persist or reconcile.

**Negative**
- A slow Claude response blocks the handler and eats into the p95 ≤ 5 s budget (tracked in §11 as accepted debt).
- Claude availability is on the critical path for task creation.

**Neutral**
- Moving to an async background parse later is possible without a data migration — it changes only the handler flow (noted in the architecture map).

## Links

- Spec: [[../spec.md]]
- SAD: [[../sad.md]] §4, §6, §8
- Related ADR: [[0004-store-timestamps-as-utc-and-anchor-relative-deadlines-to-master-timezone]]
