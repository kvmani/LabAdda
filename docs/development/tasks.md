# To-do lists implementation guide

## Read first

Scope: C1 personal/shared lists. Authoritative requirements: S8/CT-01–03 in
[SPECIFICATIONS](../../SPECIFICATIONS.md); wire contract: [C1 API](../API.md#c1-to-do-lists).
User-facing instructions: [Using to-do lists](../usage/tasks.md).
C2 workflow/history and assignment/My Tasks APIs are implemented.
[Assignment guide](task-assignment.md) covers their locks and permission boundaries.
Assignment/My Tasks web delivery is implemented; [Comments](task-comments.md) are implemented; [shared update notices](task-updates.md) are implemented.

## Source map

- backend/labadda/api/todos.py: payloads, scope checks, paging, create fingerprints,
  revision edits and detail reads. Personal owner checks never infer admin access.
- backend/labadda/models.py TodoList/TodoTask and migration0017: durable scope,
  creation identity and revisions. No deletion or scope moves in C1.
- frontend/src/pages/Todos.tsx: personal/shared UI, drafts, explicit conflict reload,
  frozen same-intent create retry and stale request/editor generations.
- backend/labadda/task_history.py, TodoChange and migration0018: atomic revision
  content history and honest legacy baselines. TaskHistory.tsx is the lazy, bounded
  browser view; actor names are current display names, IDs remain stable.
- App.tsx, components/Shell.tsx and pages/WorkspaceView.tsx: /todos and workspace
  Tasks tabs. Existing policy applies at every org level, project and group.
- backend/tests/test_todos.py and e2e/todos.mjs: scope, concurrency and browser cases.

## Invariants when changing code

Shared reads flow upward only; personal lists stay private. Resolve access from
actual list scope. No panel access. Assignment in C2 must never grant visibility.
The backend locks identity/session, then target workspace KEY SHARE before table
SHARE locks on workspaces/memberships, then the list row. This order avoids a
workspace FOR UPDATE / child-FK deadlock. Recheck session time validity immediately
before commit/replay. Preserve the actual PostgreSQL blocking regression.

Create client UUIDs bind normalized intent and destination; replay checks current
access. PUT is a full replacement with expected revision. Frontend unknown creation
results freeze the original payload for explicit same-ID retry. A late response
must not restore a denied scope or refresh another list's editor. Conflict recovery
must retain drafts until the user deliberately replaces/reviews them.

Task logical bytes are marked unmeasured in current usage accounting. C1 adds no
new configurable quota activation, reminders or automatic deletion. Pilot ceilings
are documented in the API contract; physical database totals include all tables.

## Verification and handoff

Run focused backend tests first, then scripts/verify.sh (enable real recovery as
documented in TESTING). Run e2e/todos.mjs against fresh disposable proxy fixtures;
it revokes Ben's section grant, so reset before subsequent member-dependent flows.
Check root/prefix, mobile, recovery, lost replies, conflicts and stale callbacks.
Record actual results in the roadmap; never turn planned C2 features into shipped
claims. Update this guide, API/requirements when changed, and relevant tests in the
same commit. See the latest roadmap ledger for current completion and next work.

## C1 browser recovery boundaries

List/task creation retry intent is frozen only within the current view. Latest
list/task reload is explicit and replaces its draft. A denied post-create refresh
must not select the returned list. Renaming and editor completion capture request/
editor generations, so delayed success cannot reopen denied content or repopulate
another list. Native form submit is guarded while busy; other buttons have explicit
button types. Browser regressions exercise these boundaries with synthetic users.

## C2 compatibility and history

Status and completion must agree. When status is omitted, preserve C1 fingerprints
and intermediate states on unchanged-completion edits. See task_workflow tests for
a real migration/replay fixture; adding future optional fields must not silently
invalidate older creation receipts. History is ordinary scoped content, not an
operational audit report: do not expose it through usage.read or admin privileges.
Each committed revision records changes atomically, including creator attribution;
a baseline explicitly marks unavailable earlier history. Do not auto-prune history
until its lifecycle contract exists. State/history and assignment/My Tasks APIs/web controls and [comments](task-comments.md) are delivered; shared update notices with reviewed HTTP refresh are implemented.

See the [update guide](task-updates.md) before changing shared refresh or draft lifetime.

For reviewed conversation copies and protected provenance, read the [conversion guide](task-conversion.md). Task source metadata must stay out of task/history representations except the generic provenance flag.
