# Shared task update signals

Read [task invariants](tasks.md), CT-09/T46 and the
[wire contract](../API.md#c2-shared-task-invalidation).

## Backend delivery

`backend/labadda/task_events.py` is the only task hint constructor. Routers call it
only after commit, using the actual list's workspace. It is a no-op for personal
lists. The event contains only type/workspace ID; never add list/task/comment IDs,
bodies or identities. Replay/no-op branches return before publication. No schema
change or durable event stream is introduced.

The existing Hub checks current session/read grants at delivery, maintains revoked
subscription generations and excludes task events from board-only panels. Socket
hints are unordered and lossy, including a crash between commit and publication.
Reconnect must lead to explicit authorized HTTP catch-up. Test source:
`backend/tests/test_task_events.py`, realtime tests and panel socket test.

## Browser review and catch-up

`frontend/src/taskUpdates.ts` shares existing socket subscriptions. `tasks.changed`,
`subscribed` (including reconnect) and access changes set a coalesced pending notice.
A refresh acknowledges only its starting hint generation, so a signal arriving
while HTTP reads are in flight remains pending. No request is made for each hint.

`Todos.tsx` offers **Check shared updates**: reload list navigation, then current
visible task details in place (at most 25 bounded reads). It retains the task page,
card identities, task editor and discussion drafts; it does not jump to page one
or fetch new tasks into a populated page. Use **Refresh tasks** to return to page
one and discover new tasks. List-name/editor drafts retain their original write
revisions. `TaskAssignment.tsx` retains an open choice and original revision, but
requires explicit reload if that task revision changes.

Open `TaskComments.tsx` and `MyTasks.tsx` show their own notices and explicit refresh.
Older comment pages do not acknowledge the latest-discussion hint. Revocation/
failed subscription/session end clear protected cards/pages/composers and invalidate
in-flight callbacks. A failed catch-up keeps the notice. Reconnect can signal a
possible change even when no task changed: there is no durable task event cursor.

Browser regression: `e2e/task-updates.mjs` on fresh disposable proxy fixtures; it
revokes Ben at the end. Cover root/prefix, task/comment/assignment drafts, current
page preservation, in-flight newer hints, failed reads, offline writes/reconnect,
My Tasks, actual hint payload and sibling/revocation boundaries. Run the existing
assignment/comment/task browser regressions separately after fresh proxy resets.

This is live invalidation with explicit reviewed refresh, not automatic merging or
personal cross-session updates. No notifications or comment editing/attachments.
