# C4 communication evidence

Local synthetic qualification, 2026-11-10. API stages:82a5a9a and32a9b47;
thread web:847e9e1; attachment/private-group web is the commit containing this file.

Full505 backend/recovery/drift checks and31 frontend tests/typecheck/build passed
at the attachment API boundary. Focused API evidence:30 thread/chat/realtime and25
attachment/thread/usage cases. Final browser suites:26 thread and38 attachment/
private-group checks at root/prefix, including desktop/mobile WCAG2.1 A/AA and
horizontal overflow. Independent authorization/realtime/UI findings were fixed and
re-reviewed: sequence commit order, read-receipt authority, queued reconnect,
HTTP-only replay/read cursor, stale older pages and retained new-message notices.

Five isolated authenticated researcher sessions span Thin Films and Catalysis
sections and Surface Science Division. They share a synthetic Aurora group board
and chat; Ben/Chen separately exchange validated PDFs in a two-member private group.
Four outsiders (including admin and division steward) cannot retrieve the PDF;
removing Chen stops chat/file delivery. Tests also recover lost upload and send
replies, attach a PDF to a thread reply, and prevent uncertain group creation from
blindly submitting again while exposing the committed group in navigation.

`e2e/chat-attachments.mjs <output-directory>` writes six actual screenshots,
self-contained gallery and check report. Artifacts are delivered separately as
`c4-collaboration-2026-11-10`. Existing hand-drawn SVG/native research-day sources
remain in fixtures/research-day. This new gallery's board uses native text stickies.

C4 software core is delivered: one-level threads, validated files and private-group
conversations. These are mutable groups, not a separate direct-message system.
In-memory drafts/upload controls do not survive navigation. Physical panel/site
TLS/manual accessibility gates remain open; no real-site qualification is claimed.
C5 dashboard/preferences and wider final regression follow.
