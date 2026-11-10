# C2 shared task update qualification

Local synthetic qualification on 2026-11-10. Backend base: d143b7c;
web source is the commit containing this evidence. No schema migration.

- `LABADDA_RECOVERY_TESTS=1 scripts/verify.sh`:465 backend tests, real recovery,
  no model/migration drift,31 frontend tests, typecheck and production build passed.
- `node e2e/task-updates.mjs`:30 root/prefix checks passed. Actual sockets and
  authenticated APIs verify content-free hints, sibling isolation, revocation,
  task/comment/assignment drafts, stale-editor conflict, second-page preservation,
  a new signal during a paused old snapshot, failed reads, reconnect after an
  offline write and My Tasks catch-up.
- Existing browser regressions on separately reset disposable proxy databases:
  assignment48, comments48, tasks66 passed (including desktop/mobile accessibility
  checks). Combined browser evidence:192 checks.
- Independent source review followed REVIEW.md. Four findings were corrected and
  re-reviewed: My Tasks stuck loading after revocation, failed catch-up clearing
  its notice, paginated comment drafts unmounted by refresh, and assignment choice/
  revision replaced without review. No remaining substantive finding reported.

Run the new browser script after `scripts/proxy-stack.sh start`; it revokes Ben's
section membership at the end. An optional output-directory argument saves the
shared task/editor/comment/assignment review screenshot. Capture artifacts are
separate from source. Tests use fictional identities and local assets only.

This is a single-process lossy invalidation protocol with explicit authorized HTTP
refresh, not automatic content merging. A subscribed/reconnected view can show a
notice even when unchanged. New tasks require Refresh tasks; open discussion has
its own refresh. Personal cross-session live updates and notifications are not
implemented. Site TLS/device/manual/P4 acceptance gates remain open.
