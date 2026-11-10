# Task assignment and My Tasks

Read [task invariants](tasks.md) first, then CT-07 in SPECIFICATIONS, T44 in
TESTING and [the API contract](../API.md#c2-assignment-and-my-tasks). Backend and dedicated browser assignment/My Tasks controls are implemented.
[Comments](task-comments.md) are delivered; [shared update notices](task-updates.md) are implemented.

## Source and boundaries

- backend/labadda/api/task_assignment.py: picker, assignment and My Tasks.
- TodoTask.assignee_id/relationship in models.py, migration0019: nullable identity
  and index. No grant creation, deletion, reminders or assignment notifications.
- task_history.py: before/after assignment names/IDs are scoped content history.
  Old create payloads/fingerprints stay unchanged; field edits preserve assignment.
- backend/tests/test_task_assignment.py: scope, revision, grant-filter/cursor and
  identity-lock races. Recovery integration also round-trips assignment/history.

## Web source and recovery

TaskAssignment.tsx owns eligible search, assignment choices and explicit reload
after unknown/stale writes. MyTasks.tsx owns current-source aggregation and status
filter/paging, with request generations and workspace-visibility refresh. Todos.tsx
keeps a current selected-list ref so old component saves cannot refresh another
list. Task field edits do not submit assignment fields. TaskAssignment blocks blind
retries after uncertain outcomes; it reloads task revision/history instead.
Browser regression: e2e/task-assignment.mjs (fresh disposable fixtures; revokes Ben).

## Lock ordering and final reads

Preflight current source read/write and target eligibility without target locks.
Then lock actor and target User rows in UUID order (NO KEY UPDATE), then the actor
session via lock_identity, workspace KEY SHARE/table SHARE, and list row. Resolve
eligibility again after the scope lock; session validity again before acceptance.
Do not move target locks after actor/session/list locks: reciprocal assignments can
otherwise deadlock. Preserve the PostgreSQL blocked-target-deactivation regression.

Picker results are eligible at their query snapshot; never treat an option as an
access grant. My Tasks uses current source policy, rechecks the principal/grants
before returning, drops revoked rows and suppresses all pagination cursors when
grants change. Removed members' assignment rows remain for history/reassignment,
but they cannot read shared tasks through My Tasks. Do not silently clear them.

Run test_task_assignment.py with task_workflow and real recovery, then the affected
browser flows. Fixtures recreate the test schema; do not run concurrent pytest
sessions against the same database. Update this guide, API and ledger with code.

Explicit assignment reload reads the current task even if its revision is unchanged.
Do not rely solely on a revision-change effect to unfreeze an uncertain choice: a
request can fail before reaching the server. Preserve that browser regression.

Open assignment drafts keep their original revision. Shared refresh preserves the
choice but blocks saving after a revision change until explicit assignment reload.
