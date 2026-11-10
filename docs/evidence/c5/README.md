# C4–C5 final local qualification

Source is the commit containing this record, following stages82a5a9a,847e9e1,
32a9b47,6d5c610 and989e551. Captured2026-11-10; all fixtures are synthetic.

- Full `LABADDA_RECOVERY_TESTS=1 scripts/verify.sh`:519 backend cases including
  real recovery, no model/migration drift,31 frontend cases, typecheck/build passed.
- Final root/prefix browser suites: preferences30, dashboard24, threads26,
  attachment/private-group38, tasks66, live tasks30, main chat/board/panel69,
  conversation conversion44, board references42. Total369 distinct checks passed.
  Includes desktop/mobile WCAG2.1 A/AA/overflow, lost replies, concurrent settings,
  held response/reconnect/history races, source revocation and five researcher flows.
- Independent source reviews across API/UI/security/realtime slices completed with
  findings corrected and re-reviewed. Owner category choices preserve existing
  alerts, apply to new occurrences and do not replay skipped reminder occurrences.
- [Bounded TLS workload report](workload.json):30 clients,8 drawers,22 readers,
  two sibling workspaces,90-second workload.1646 board operations and144 chats;
 26850 expected deliveries, none missing; zero lost/duplicate/isolation errors and
  no revision gaps. Update p95 61.3ms; list p95 98.4ms; both targets enforced/passed.
  This is a bounded regression, not the15-minute representative-site acceptance.
- Development8000/research8010 migrated/restarted through0025 with preserved
  settings, ready200 and checked existing content/task counts unchanged. No reset.
- Ten actual screenshots plus offline review gallery/ZIP are delivered separately
  as labadda-c4-c5-review-2026-11-10. The C4 shared board uses native text stickies;
  existing handwritten SVG/native research-day fixtures remain available unchanged.

C4 software core and C5 dashboard/preferences/local automated qualification are
complete. Physical panel, representative-site/full workload and manual screen-reader/
visual acceptance remain open. Automated task reminders/assignment alerts, personal
cross-session task delivery and optional per-object/history board views are not
claimed. P5 archive expansion remains deferred by the owner.
