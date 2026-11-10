# C3 conversation-to-task qualification

Local synthetic qualification on 2026-11-10. Backend source: a275059; web source is
the commit containing this evidence. Schema0021 is additive and guards lossy downgrade.

- Full `LABADDA_RECOVERY_TESTS=1 scripts/verify.sh` passed480 backend tests,
  real recovery, model/migration drift check,31 frontend tests, typecheck and build.
  Final UI accessibility/layout refinements also passed frontend tests/typecheck/build.
- `e2e/task-conversion.mjs` passed44 root/prefix checks: reviewed post/chat copies,
  audience confirmation/reset, frozen lost-reply retry, private/sibling boundaries,
  destination paging, safe text display, source-only revocation with a delayed first
  response, desktop/mobile axe WCAG2.1 A/AA and overflow checks. A MutationObserver
  checks that a delayed revoked source body is never briefly restored to the DOM.
- Existing browser regressions passed on separately reset fixtures:69 chat/board/
  panel/account flows,66 task checks and30 shared live-update checks. Combined with
  conversion44, this stage has209 browser checks at root/prefix.
- The independent authorization review found and verified fixes for hidden previous
  list selection on paging and stale source restoration while a response was held.
  No remaining substantive finding was reported. Backend review included actual
  source locks, populate_existing, current source/destination authority, atomicity,
  replay, purge behavior, downgrade and recovery.
- Existing development8000 and research8010 demos migrated/restarted with their
  preserved settings, ready200 on0021. Checked existing identity/workspace/content/
  task counts were unchanged; no reset/reseed or grant changes were performed.

Browser scripts use separately reset disposable proxy databases; conversion revokes
Ben's source grant last. Build before browser startup. The preserved demos are not
browser-test reset targets. See the latest roadmap entry for regression totals.

Limits: reviewed plain-text title/description copies, not synchronized conversations.
Source attachments/authors/names do not get copied automatically. Generic provenance
is visible to destination task readers; protected source content still needs its own
current grant. Reply conversion, whiteboard references, notifications and physical/
site/manual acceptance remain separate work. No real-site acceptance is claimed.
