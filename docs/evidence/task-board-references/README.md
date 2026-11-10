# C3 board reference qualification

Local synthetic qualification on 2026-11-10. Backend source: e822ffd; web source is
the commit containing this evidence. Schema0022 extends existing protected task
provenance with an immutable numeric board context.

- Full `LABADDA_RECOVERY_TESTS=1 scripts/verify.sh` passed492 backend tests, real
  recovery, schema drift check,31 frontend tests, typecheck and production build.
- Focused board/conversation API suite:27 passed, including real PostgreSQL row-lock
  waits, replay after ink/restore, rollback, expiry, source grant loss and purge,
  populated downgrade and dual-grant source lookup.
- New board browser suite:42 checks at root/prefix, including stale context with
  draft preservation, explicit refresh, unknown-write freezing, recovery after ink,
  restore, protected recorded/current metadata and live link, audience confirmation,
  sibling denial and delayed source-only revocation. A MutationObserver catches
  transient restoration of revoked context. Form/source view pass WCAG2.1 A/AA
  axe and overflow checks at1400px and390px.
- Existing post/chat conversion suite:44 checks passed after shared-form/source-view
  changes. Existing chat/board/panel flows69, task checks66 and live task updates30
  also passed. Combined browser evidence:251 checks (42+44+69+66+30).
- Independent authorization/UI review found a final-refresh purge race; fixed by
  capturing primitive IDs before ORM expiry. Added regressions for board and post
  hard purge. Fixes, shared helper and UI were re-reviewed with no remaining
  substantive finding. Reviewer did not run a competing test database session.
- Preserved development8000 and research8010 demos migrated/restarted with existing
  settings, ready200 on0022 and checked existing content/task counts unchanged.
  No reset/reseed, source-content copy or grant change was performed.

Use fresh disposable proxy fixtures for each browser script; new board suite
revokes Ben's source section grant last. Keep preserved demo databases out of resets.
The existing panel regression explicitly excludes the new task action.

This stores recorded context, not a historical render or image. Source inspection
requires current task AND board grants; only generic provenance is destination-
visible. Object/region references, historical viewing, reply conversion and site/
manual/device acceptance remain separate work. No new quota or retention policy.
