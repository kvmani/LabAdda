# Task discussion implementation

Read [task invariants](tasks.md), CT-08/T45 and the [comments API](../API.md#c2-immutable-task-comments).
Discussion remains immutable with explicit HTTP refresh. Shared update notices are
implemented in the [update guide](task-updates.md); no notifications are sent.

## Source map

- backend/labadda/api/task_comments.py: actual task/list scope, normalized request
  identity, current-session checks, latest-first bounded pages and append ceiling.
- TodoComment in models.py and migration0020: per-author client ID uniqueness,
  per-task monotonic sequence, body and current public author lookup. Sequence
  allocation occurs under the existing list lock; it does not change task revision.
- frontend/src/components/TaskComments.tsx: lazy page/composer, frozen uncertain
  create retry, request generations and plain-text display. Todos.tsx retains
  same-list cards during task reloads, preserving discussion drafts; choosing
  another list or denied refresh still clears protected data.
- test_task_comments.py and e2e/task-comments.mjs: scope, retry/sequence/expiry,
  shared/personal discussions, draft preservation, plain-text rendering and mobile.
  Recovery integration includes a real restored comment.

## Contracts to preserve

Check the actual task belongs to the requested list before reads/replay/writes.
Reuse identity/scope/list locks and recheck time validity before acknowledgement.
Normalize text before fingerprinting; do not infer sharing from authorship or
assignment. A new comment never advances the task field revision or sends a
notification. Reads recheck current grants after serialization. Unknown creation
outcomes retain client ID and original text in the open view; no automatic replay.
Personal discussion stays owner-only, including against administrators.

Comments are escaped text, not HTML/Markdown execution. Preserve newlines and
Unicode. Build assets before starting browser flows; do not replace dist while
browser tests load it. Fresh proxy fixtures are required between scripts that
revoke Bharat or change posting policy. Full backend tests share a destructive test
schema, so never run simultaneous pytest sessions against it.

Shared invalidation was independently reviewed; preserve its delivery/revocation
boundaries. In particular, do not
broadcast personal task/comment bodies or IDs into workspace channels. Comment
editing/deletion and history retention require future explicit contracts.
