# Colleague chat implementation

Read S3/S8 and the latest roadmap ledger. C4 work proceeds as APIs, threaded web,
attachment APIs, attachment/private-group web qualification; C5 dashboard/settings
follow. Keep each slice runnable and update this guide with its source/test contract.

Current baseline: workspace stream with durable client IDs, per-workspace unread
state, socket delivery and HTTP replay. Groups use the same source policy. Parent
membership and administrator roles never grant access to private groups or siblings.
Board-only sessions never receive chat. No implicit broader sharing of attachments.

## Thread API (schema0023)

ChatMessage.parent_id is immutable through APIs and names a root in the same source.
chat.py owns validation, bounded thread pages and post-commit messages. Reuse the
shared actor/metadata lock primitives in todos.py; send additionally locks workspace
NO KEY UPDATE before allocation so lower sequences cannot commit later. Read
receipts lock current read scope and identity before commit. No source access is
created by parent IDs. Never advance browser catch-up solely from live message max.
Backend tests: test_chat_threads, existing test_chat_board/test_realtime and recovery.
Web threads and attachments are following slices, not delivered by this API stage.

## Thread web controls

Chat.tsx keeps a safe HTTP cursor separate from live display, queues reconnect
catch-up behind active requests and acknowledges only authorized HTTP snapshots.
The bounded earlier-history view pauses live replacement until Return to latest;
view generations reject late older pages. ChatThread.tsx pages/reloads one root and
retains ChatComposer state. ChatComposer freezes unknown text/parent identity for
explicit same-request recovery. Scope generations and socket denial clear all
protected streams, threads, dialogs and composers. Browser: e2e/chat-threads.mjs,
including held-response reconnect/older-page races and desktop/mobile axe checks.
Attachments/private-group qualification are following slices.

## Attachment API (schema0024)

Asset.chat_message_id is a third exclusive durable destination alongside post/board.
No private upload becomes shared before message commit. chat.py locks canonical
provisional IDs in UUID order, binds owner/status and freezes them in replay intent.
ChatMessage.attachments loads in bounded batches; message_json uses the instance API
prefix for URLs. files.py checks the actual chat source before desktop delivery;
board-only panels still see only own-board embedded images. workspace_usage.py joins
chat sources so retained original/preview counts stay accurate. Existing upload
reservation/receipt/preview validation and asset recovery are reused, not bypassed.
Tests: test_chat_attachments plus upload/file/usage/recovery regressions. Web file
controls and private conversation qualification follow in stage4.

## Attachment and private-group web delivery

ChatComposer uses the existing UploadQueue/UploadRecovery receipt controls. Pending
uploads block send; unknown sends freeze original text/root/file IDs; no implicit
re-upload or rebind. ChatFiles displays authorized links/previews in stream and
thread. NewGroup's conversation mode selects one colleague and opens a private
group chat; it freezes uncertain creation and refreshes group navigation rather
than automatically retrying. Group membership remains explicit and mutable.
Browser qualification: e2e/chat-attachments.mjs creates five synthetic users across
two sibling sections/one division, a common plan group and a separate two-person
file handoff. It verifies upload/send recovery, private file isolation, reply files,
mobile/desktop axe, uncertain group creation and membership removal. Gallery/report
are separate artifacts. No direct-message endpoint or implicit attachment sharing.
