# Task discussion evidence

Synthetic validation on 2026-11-10: full461 backend tests with real recovery and
migration drift checks; frontend typecheck,31 tests and build passed. The focused
comment suite has15 cases. Independent authorization/idempotency and UI review
found no substantive issue. Real recovery preserves discussion ID/body.

`e2e/task-comments.mjs` passed48 root/prefix browser checks: five users across
sibling sections and their division, personal isolation, author attribution,
unknown creation replay exactly once, escaped HTML-looking text, draft preservation
through same-list refresh and field edits, stale page suppression, actual read-only
policy, direct-write denial, final grant revocation and desktop/mobile axe/overflow.
Output screenshots default to /tmp/labadda-task-comments. Wait for posted list-item
text, not a matching textarea value, before checking another reader's result.

Final assignment regression passed48 checks, including an unknown write that never
reached the server (same revision after explicit reload). Existing task regression
passed66 checks:162 browser checks on this slice. The first regression startup ran
while assets were being rebuilt and failed to find the login form; the sequential
build-before-start rerun passed. No formal root-cause claim beyond that observation.
Readonly browser fixtures use the actual steward posting-policy route, not admin
workspace metadata. Both scripts revoke membership/change policy; reset the proxy
fixtures before other dependent flows. Automated evidence does not replace manual
accessibility, physical panel or real-site acceptance.

Final local-demo refresh migrated development and research instances to0020,
restarted each with its preserved application settings, and verified readiness200.
Checked counts for users/workspaces/posts/chat/boards/ops/assets/notes and existing
to-do lists/tasks/history/comments were unchanged. This is local synthetic evidence,
not pilot activation.40 local documentation file links resolved across the entry
map, repository instructions and feature/user guides.
