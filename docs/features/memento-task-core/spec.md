---
status: Draft
owner: "Product Owner"
reviewers: ["Tech Lead"]
updated_at: "2026-07-15"
feature_size: "M"
---

# Spec — memento-task-core

> **Reference module / docs / channels used:** `bot/config.py` · `bot/shared/claude_client.py` · `bot/shared/exceptions.py` · `bot/shared/scheduler.py` · `bot/main.py` · `docs/architecture-map.md`

## 1. Context

Verbal commitments made during team communication ("I'll send the mockups by EOD") are routinely missed because there is no accountability loop: the commitment is heard, noted mentally, and forgotten — by both parties. The Worker has no system reminder before the deadline; the Master has no structured prompt to check whether the work actually arrived. This gap affects every team that coordinates via Telegram and relies on individual trustworthiness rather than documented proof.

Memento task-core is the foundational feature that closes this loop. It is the first feature of the Memento bot, and every downstream feature (statistics, reporting, escalation) depends on the audit trail it creates. Without it, no meaningful accountability data exists.

The committed approach is a three-part capture–remind–verify loop: a task commitment (Master-assigned or Worker self-committed) is captured in the configured group chat (`MASTER_GROUP_CHAT_ID`) via an explicit `/task` command; a timed reminder reaches the Worker privately 5 minutes before the deadline; at the deadline, the Master receives a private outcome prompt and records Done, Failed, or Extended. Every outcome is persisted. Extended tasks re-enter the cycle with a new Master-supplied deadline.

No direct competitive equivalent closes all three steps in a single Telegram-native flow. Adjacent tools (Planyway, Taskade, Geekbot, Friday.app) either require context-switching to external systems or operate on polling/standup cadence rather than per-commitment deadline enforcement with a structured Master verdict.

## 2. Goals

- Every verbal commitment made in the group chat is captured with a deadline and a named Worker before the conversation moves on.
- Every deadline fires a private outcome prompt to the Master that records a structured verdict (Done / Failed / Extended), creating a persistent audit trail.
- Extended tasks re-enter the full accountability cycle without manual re-entry.

## 3. Non-goals

- Per-Worker completion statistics and dashboards — planned as a separate `stats` feature.
- Passive commitment detection: bot auto-intercepting "I'll do X by Y" without an explicit trigger — deferred to v2.
- Multi-Master configuration — architecture constraint: a single Master is identified by `MASTER_TELEGRAM_ID` in configuration; multi-Master is out of scope.
- Multi-assignee tasks — one Worker per task in v1; group accountability is a future feature.
- Auto-escalation or auto-resolution when Master does not act at deadline — task sits pending; re-prompt is a v2 concern.
- Per-user timezone configuration — the entire team shares a single `MASTER_TIMEZONE` config var (IANA timezone string); per-user or per-task timezone overrides are out of scope for v1.
- Task capture in any chat other than `MASTER_GROUP_CHAT_ID` — the bot ignores `/task` commands in other groups or in private chats.

## 4. User stories

### US-01: Master assigns task to Worker
**As a** Master
**I want** to send `/task @Worker <description> <deadline>` in the group chat
**So that** the commitment is documented and the Worker is notified privately

### US-02: Worker self-commits to task
**As a** Worker
**I want** to send `/task <description> <deadline>` (with no `@Worker` mention) in the group chat
**So that** the commitment is documented and overseen by the Master

### US-03: Worker receives pre-deadline reminder
**As a** Worker
**I want** to receive a private reminder 5 minutes before my task deadline
**So that** I have a final prompt to complete the work on time

### US-04: Master records outcome at deadline
**As a** Master
**I want** to receive a private prompt at the deadline and mark the task Done, Failed, or Extended
**So that** the outcome is recorded in the audit trail

### US-05: Master extends deadline
**As a** Master
**I want** to set a new deadline when extending a task
**So that** the accountability loop restarts with the updated commitment

### US-06: Worker notified of outcome
**As a** Worker
**I want** to receive a private notification when the Master marks a task Failed or Extended
**So that** I know the Master's verdict and any new deadline

### US-07: Worker views open tasks
**As a** Worker
**I want** to list my open tasks
**So that** I can see all active commitments at a glance

### US-08: Master views Worker's open tasks
**As a** Master
**I want** to list open tasks for a specific Worker
**So that** I can monitor what each person currently owes

## 5. Acceptance criteria

### AC-01 (US-01) — happy path
**Given** the Master sends `/task @Worker <description> <deadline>` in the configured group chat (`MASTER_GROUP_CHAT_ID`), where `@Worker` is a Telegram mention of the assignee
**When** the bot processes the message
**Then** the task is recorded with the Worker as assignee, the Master as overseer, the parsed deadline, and status "open"; the Worker receives a private message acknowledging the task with its title and deadline; the group chat receives a confirmation naming the Worker, the task title, and the deadline in the team's configured timezone

### AC-02 (US-02) — happy path
**Given** a registered Worker sends `/task <description> <deadline>` (with no `@Worker` mention) in the configured group chat
**When** the bot processes the message
**Then** the task is recorded with the sender as assignee and the Master as overseer; the Worker receives a private acknowledgement; the Master receives a private notification of the new commitment

### AC-03 (US-03) — happy path
**Given** a task with status "open" exists and its deadline is approaching
**When** 5 minutes remain until the deadline
**Then** the Worker receives a private message naming the task title and the exact deadline time in the team's configured timezone; if fewer than 5 minutes remained at task creation time, the reminder fires immediately upon task creation instead

### AC-04 (US-04) — happy path: Done
**Given** the Master receives an outcome prompt at the deadline containing the task title, the Worker's name, and the deadline in the team's configured timezone
**When** the Master taps "Done"
**Then** the task is recorded with status "done" and a `resolved_at` timestamp; no further notifications fire for this task

### AC-05 (US-04, US-06) — happy path: Failed
**Given** the Master receives an outcome prompt at the deadline containing the task title, the Worker's name, and the deadline in the team's configured timezone
**When** the Master taps "Failed"
**Then** the task is recorded with status "failed" and a `resolved_at` timestamp; the Worker receives a private notification stating the task was marked failed by the Master

### AC-06 (US-04, US-05, US-06) — happy path: Extended
**Given** the Master receives an outcome prompt containing the task title, the Worker's name, and the deadline in the team's configured timezone, and taps "Extended"
**When** the Master provides a new future deadline
**Then** the task's deadline is updated and the extension is recorded with a timestamp; status returns to "open"; the Worker receives a private notification stating the task was extended with the new deadline; a new pre-deadline reminder and outcome prompt are scheduled for the updated deadline

### AC-07 (US-07) — happy path
**Given** a registered Worker sends the list-tasks command to the bot in private
**When** the bot processes the command
**Then** the Worker receives a private message listing all their open tasks with title and deadline in the team's configured timezone; re-extended tasks appear identically to new open tasks (no extension count in v1); if no open tasks exist, the bot states there are none

### AC-08 (US-08) — happy path
**Given** the Master sends the list-tasks command specifying a Worker
**When** the bot processes the command
**Then** the Master receives a private message listing all open tasks assigned to that Worker with title and deadline in the team's configured timezone; re-extended tasks appear identically to new open tasks; if no open tasks exist for that Worker, the bot states there are none

### AC-09 (US-01, US-02) — error: unparseable or invalid deadline
**Given** the Master or a Worker sends `/task <body>` in the configured group chat whose deadline the bot cannot resolve to a specific date and time, or whose resolved deadline is in the past
**When** the bot attempts to process the message
**Then** no task is created; the sender receives a message in the group chat explaining the issue and asking them to rephrase with a clearer time reference. Relative deadlines (e.g. "by EOD", "in 2 hours") are resolved against the team's `MASTER_TIMEZONE` at the time the message is received.

### AC-10 (US-01) — authorization: only Master assigns tasks to others
**Given** a non-Master user sends `/task @OtherUser <description> <deadline>` attempting to assign a task to another user
**When** the bot processes the message
**Then** no task is created and the sender receives a message stating they are not authorized to assign tasks to others

### AC-11 (US-04) — authorization: only Master receives outcome prompt
**Given** a task reaches its deadline
**When** the outcome prompt is delivered
**Then** only the Master receives the Done / Failed / Extended prompt; no Worker receives an actionable outcome prompt

### AC-12 (US-01, US-02) — cross-context: task creation requires registered Worker
**Given** the bot receives a `/task` message naming a person (via Telegram `@mention`) who has not started a private conversation with the bot
**When** the bot processes the message
**Then** no task is created; the sender receives a message stating the named person must start the bot in private before tasks can be assigned to them. A registered Worker is defined as any user who has previously initiated a private conversation with the bot.

### AC-13 (US-04) — domain invariant: outcome idempotency
**Given** the Master has already recorded an outcome for a task, or the task is in a state no longer awaiting an outcome at the deadline associated with the prompt
**When** the Master taps an outcome button on any outcome prompt for that task
**Then** the system ignores the action; the task outcome is unchanged; the Master sees a message confirming the outcome was already recorded or that the prompt is no longer active

### AC-14 (US-05) — domain invariant: extended deadline must be future
**Given** the Master taps "Extended" and submits a new deadline via the private outcome prompt
**When** the submitted deadline is in the past or fewer than 5 minutes from now
**Then** the system rejects the new deadline and asks the Master privately to provide a deadline at least 5 minutes in the future

## 6. Non-functional requirements

| Aspect | Target | Measurement |
|---|---|---|
| Task creation latency p95 | ≤ 5 s end-to-end (including deadline parsing) | Per-request timing logged in task handler |
| Pre-deadline reminder drift | ≤ 60 s from scheduled time | Compare job fire timestamp vs scheduled time in logs |
| Deadline outcome prompt drift | ≤ 60 s from task deadline | Compare prompt delivery timestamp vs task deadline in DB |
| Scheduler job durability | Zero jobs lost across bot restarts | SQLAlchemy job store verified by integration test: schedule job → restart → confirm job fires |
| Notification delivery success | ≥ 99% for registered Workers | Log and alert on DM delivery failures |
| Availability | ≥ 99.5% uptime, monthly window | Process monitor + polling health check |

## 6.1 Security / privacy

- **Data classification:** Internal — task titles, deadlines, and outcomes are operational team data; not public.
- **Personal data touched:** Telegram user IDs (integer), display names (string, user-provided), chat IDs. No government IDs, financial or health data.
- **AuthZ/AuthN impact:** The Master is identified by the `MASTER_TELEGRAM_ID` configuration value; only this Telegram user ID may assign tasks to others and record outcomes. The group chat is identified by `MASTER_GROUP_CHAT_ID`; `/task` commands in other chats are silently ignored. Workers may only self-commit; they cannot assign tasks to other users or act on outcome prompts. The bot validates caller identity against the stored user ID on every outcome-prompt callback. A registered Worker is any user who has initiated a private conversation with the bot; the bot acts on Telegram user ID from `@mention` entities, never on display names.
- **Abuse cases:**
  - Worker attempts to assign a task to another Worker: system denies and explains authorization; no task created.
  - Master receives duplicate outcome prompt (stale message replay): idempotent handler ignores the second tap; outcome does not change.
  - Impersonation via display name: bot always acts on Telegram user ID, never on display name; display names are for human-readable output only.
- **Security review:** N/A — no new authorization boundaries beyond the `MASTER_TELEGRAM_ID` and `MASTER_GROUP_CHAT_ID` identity checks; no PII beyond Telegram user IDs already present in the Telegram platform.

## 7. Metrics / KPIs

- **Task creation rate** — baseline: 0 (new feature), target: ≥ 5 tasks created per active work day within 30 days of launch.
- **Master outcome resolution rate** — baseline: 0, target: ≥ 80% of deadline outcome prompts resolved (Done / Failed / Extended) within 24 hours of firing, within 30 days of launch.
- **Pre-deadline reminder delivery rate** — baseline: 0, target: ≥ 99% of scheduled reminders delivered within 60 seconds of scheduled time, within 30 days of launch.
- **Failed task rate** — baseline: 0, target: tracked and queryable in DB within 30 days of launch (no numeric target — feeds the future statistics feature).

## 8. Open questions

- [ ] Pending limbo escalation: should Master receive a re-prompt after 24 h of no action on an outcome prompt? Default now: no auto-escalation in v1 — task stays pending. — owner: Product Owner, due: before sdd:tasks
- [ ] `update_display_name` (users/repo.py) relies on ORM `onupdate=func.now()` for `updated_at` rather than setting it explicitly, unlike tasks/repo.py mutators. DB-observable outcome is correct; fix is cosmetic parity. Test for /start only asserts `display_name`, not `updated_at`. — owner: Tech Lead, due: before next feature touching users
- [ ] `_split_body` deadline heuristic (tasks/handler.py:34-45) splits on the first keyword in `[by, until, before, in, at, due, on]`; multi-word titles containing those words produce a truncated title and a long deadline tail. Claude may still parse correctly; AC-09 error path is the safety net. Known v1 fragility — owner: Tech Lead, due: before stats feature (feeds task titles into reports)

---

_Clarify edits log (2026-07-15) — 13 resolved, 0 deferred:_
- `under-specified-AC · §AC-01/§AC-02 · resolved · "natural-language message" → explicit /task command; Worker identified via @Telegram mention`
- `under-specified-AC · §AC-02 · resolved · self-commit assignee → always the sender (no @mention parsed)`
- `under-specified-AC · §AC-01 · resolved · "brief public confirmation" → confirmation naming Worker, task title, deadline in team timezone`
- `missing-actor · §AC-12/§AC-15 · resolved · "registered Worker" = any user who has DM'd the bot; AC-15 behavior wins (reject task if not registered); original AC-12 removed`
- `under-specified-AC · §1/§AC-01/§AC-02 · resolved · "the group chat" → MASTER_GROUP_CHAT_ID env var; /task ignored in other chats`
- `conflicting-requirement · §AC-09/§AC-14 · resolved · Extended deadline rejection goes privately to Master; AC-09 scoped to initial creation in group chat`
- `under-specified-AC · §AC-09 · resolved · relative deadlines anchored to MASTER_TIMEZONE at message receipt time`
- `under-specified-AC · §AC-03 · resolved · sub-5-min at creation → task accepted; reminder fires immediately`
- `unstated-assumption · §AC-04/§AC-05/§AC-06 · resolved · outcome prompt includes task title, Worker name, and deadline; unlimited concurrent tasks per Worker`
- `vague-term · §AC-06/§AC-07/§AC-08 · resolved · "open" is undifferentiated; re-extended tasks appear identically in listings (v1)`
- `under-specified-AC · §AC-13 · resolved · idempotency keyed on task-state, not per-message`
- `under-specified-AC · §AC-14 · resolved · Extended deadline rejection sent privately to Master`
- `under-specified-AC · §AC-04/§AC-05/§AC-06 · resolved · Failed and Extended persist resolved_at / extension timestamp`
