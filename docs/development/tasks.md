# To-do lists implementation guide

## Read first

Scope: C1 personal/shared lists. Authoritative requirements: S8/CT-01–03 in
[SPECIFICATIONS](../../SPECIFICATIONS.md); wire contract: [C1 API](../API.md#c1-to-do-lists).
User-facing instructions: [Using to-do lists](../usage/tasks.md).
C2 assignment/comments/history/live updates and My Tasks remain planned.

## Source map

- backend/labadda/api/todos.py: payloads, scope checks, paging, create fingerprints,
  revision edits and detail reads. Personal owner checks never infer admin access.
- backend/labadda/models.py TodoList/TodoTask and migration0017: durable scope,
  creation identity and revisions. No deletion or scope moves in C1.
- frontend/src/pages/Todos.tsx: personal/shared UI, drafts, explicit conflict reload,
  frozen same-intent create retry and stale request/editor generations.
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
