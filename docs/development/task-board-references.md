# Research-plan and whiteboard task references

Read [task invariants](tasks.md), [conversation conversion](task-conversion.md),
CT-11/T48 and the [API contract](../API.md#c3-protected-whiteboard-context).

## Source map

- `api/task_board_conversion.py`: bounded context lookup, current-board validation,
  creation receipt and protected source metadata. Shared lock helper lives in todos.
- `TodoSource`/schema0022: nullable Board FK with SET NULL and recorded epoch/revision;
  at most one post/chat/board source, coherent bounded tuple, guarded downgrade.
- `Board.tsx`: normal-session Create task from board action; no panel action/form.
- `ConversationTask.tsx`: shared audience/list/draft/retry UI with a typed board
  variant; context never follows later ink implicitly. Explicit refresh keeps text
  and clears confirmation; unknown-write retry keeps its original tuple frozen.
- `TaskSource.tsx`: generic source control, dual-grant inspection, recorded/current
  tuple and explicitly live board link. Existing all-readable-scope guards prevent
  delayed first responses restoring metadata after access loss.

## Contracts to preserve

This is immutable numeric context, **not** a saved board image or archived render.
Use published immutable board snapshots when an image copy is needed. A plan can
already consist of native handwritten strokes/stickies or board images; references
copy none of these. Never insert a Board for a read-only source reader. A never-
written board needs content before the normal UI enables task creation.

Lock identity/session, destination list/scope and source read scope as in CT-10,
then actual Board FOR SHARE with populate_existing. Check new request context only
after checking for a committed task receipt. A retry after board edits/restore
must recover its original task instead of failing a new-context test. References,
history and tasks commit together, then publish only a content-free destination
hint. Current source-read and destination-write rules also apply to replay.

Source retrieval uses current task and board grants and a final read check. Capture
primitive IDs before expiring ORM rows: source purge during final refresh must
return uniform404, not ObjectDeletedError. This also applies to post sources.
Source purge clears its FK; stored tuple still blocks lossy downgrade. Ordinary
list/task/history/My Tasks/events never include board context or topology.

Backend/API and web controls are delivered; see the [qualification evidence](../evidence/task-board-references/README.md). Checks: focused board/conversation tests, real
recovery, full verify, new browser suite and post/chat/board/panel regressions.
Board-source storage bytes are not separately metered; no quota/retention changes.
Per-object/region links, historical board viewing and cross-session personal task
signals remain outside this slice. C4 communication follows C3 core delivery.
