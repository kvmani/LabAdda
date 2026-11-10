# Conversation-to-task implementation

Read [task invariants](tasks.md), CT-10/T47 and the
[API contract](../API.md#c3-conversation-to-task).

Backend and web controls are delivered. Qualification evidence is recorded in the
[ledger](../../ROADMAP.md) and [capture/check notes](../evidence/task-conversion/README.md).

## Sources and scope

- `api/task_conversion.py`: readable post/chat, explicit audience, creation and
  independent protected source view. No reply/board conversion yet.
- `api/todos.py`: shared `_create_task_row` staging helper; old create identity and
  task fields remain compatible. Conversion fingerprints bind the extended intent.
- `TodoSource`/schema0021: one task reference, separate nullable post/chat foreign
  keys, never both populated. Source purge sets its FK null; generic provenance
  remains, while protected retrieval returns404. Populated downgrade is refused.
- `ConversationTask.tsx`: editable reviewed copy, current writable destinations,
  bounded list picker, explicit confirmation, frozen unknown-write retry.
- `TaskSource.tsx`: lazy protected source body as text. Guard all currently readable
  workspace subscriptions before the first response; revoke/visibility changes
  invalidate in-flight bodies even when the source workspace is not yet known.
- Chat and Noticeboard offer creation; Todos renders the source control only when
  generic `has_source` is true. This boolean is intentionally destination-visible;
  never add source IDs, names or content to tasks/history/My Tasks/task events.

## Locking and failure invariants

Lock actor/session, then destination using existing task list scope locks. Shared
scope locks include workspace/membership SHARE table locks; for a personal target,
lock the source workspace KEY SHARE before acquiring these table locks. Source
read authority and destination write authority must both hold under those locks.
Lock the actual source row FOR SHARE with `populate_existing` before acceptance:
a delete committed while waiting must not leave cached preflight data valid.
Finish with the current time-valid identity check. Creation/history/reference
commit together; only a new shared commit emits a hint. Never move acknowledgement
or source expansion before that boundary.

The reviewed task copy survives source edit/removal/revocation. Its reference
requires current task AND source access on every request. Recheck reads after
serialization. Generic404 covers all unavailable references; no admin bypass.

Unknown creation outcomes retain list ID, UUID, original text and confirmation;
no blind new request. Destination/list changes reset confirmation, and list paging
clears any hidden previous selection. Revocation clears forms/views and invalidates
late responses. Drafts remain in memory, not across navigation. New tasks use
existing field/assignment/workflow controls after creation.

Run T47 and real recovery, full verify, then the conversion browser suite and
existing chat/task regressions on separately reset disposable proxy databases.
Independent authorization review is required by REVIEW.md. Do not reset preserved
development/research demos. No source reference accounting, retention action,
attachments, source edits or board context is introduced in this slice.
