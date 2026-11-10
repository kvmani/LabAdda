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
