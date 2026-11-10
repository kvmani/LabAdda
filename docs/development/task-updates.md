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

Backend delivery is implemented. Browser notices and reviewed refresh are the next
slice; do not claim automatic task convergence, personal cross-session updates,
notifications or comment editing/attachments.
