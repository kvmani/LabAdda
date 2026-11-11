# Staff records and people management

Read the [P1 card](../plan/people.md#p1--staff-record-people-list-and-profile),
[PO-01–03 and PO-20](../PEOPLE-AND-ORG.md), then the
[console guide](admin-console.md). Staff administration grants no private content access.

## Foundation (P1 slice, implemented)

Schema0026 extends `User` with optional staff/contact fields and dates, a unique
employee number, checked employment status and positive revision. Active legacy
accounts become active, password-setup-required accounts invited, disabled accounts
left. Historical dates remain unknown; no date or employee number is invented.
`people.set_status` is the single production writer of `is_active`; invited accounts
remain eligible to activate but cannot normally sign in until password setup.
On leave retains access by default; an explicit `leave_sign_in=False` stores
blocked leave using the existing access switch. Other statuses reject that option.
Legacy access toggles on a leave record preserve its leave state. Existing credential reset does not change an
active employee's employment status. Legacy enable/disable remains compatible,
mapping to active/invited/left; reviewed lifecycle changes arrive in P2/P3.

Creation, activation, legacy identity changes and operator admin creation keep
status/revision consistent; transactional audit events include status before/after
and access before/after for legacy toggles. Existing deactivation still revokes sessions and
revalidates sockets after commit. `set_status` only maintains staff fields; its
caller must retain the existing revocation/audit/commit/revalidation protocol.

Normal successful sign-in records only a site-calendar date in `last_seen_on`.
An atomic greatest-date update prevents concurrent older observations from moving
it backwards. Panel claims do not produce normal sign-in observations; ordinary
reads do not write it. Observation does not increment the staff revision. Old
session timestamps are not exposed through a new API.

## Migration and recovery checks

`test_staff_migration.py`: populated0025 backfill, unknown dates, uniqueness/checks,
reconstructible downgrade and refusal to drop any novel staff metadata/date/state.
`test_people_state.py`: status/boolean mapping, activation, deactivation/revocation,
site-calendar boundary, date-only monotonic observation and panel isolation.
`test_recovery_integration.py` preserves staff fields/revision/date with content.

Older migration-guard tests use `tests/migration_helpers.py` to remove only their
synthetic P1 metadata before testing earlier downgrade guards. This preserves all
original protected data/assertions; otherwise every login's new staff date would
correctly stop the chain before reaching the older guard being tested. P1's own
lossless-downgrade tests never use this fixture-preparation helper.

## Read-only API

`api/people.py` exposes the directory, profile, access, timeline and report routes
in [API P1](../API.md#p1-directory-reads). `people_directory.py` owns literal
search/home-unit/direct-role filters and filter-bound keyset cursors; nulls stay
last in both sort directions. `people_profile.py` owns explicit record fields,
retained/direct/upward grant metadata and date-only staff history. It never
forwards raw audit JSON or unknown free-form reasons.

`people_export.py` materializes at most10,000 filtered rows, escapes spreadsheet
formulas (including control/Unicode prefixes), emits UTF-8 BOM and audits only row
count. Delivery rechecks authority after the audit commit; report preparation is
not proof a browser saved the file. Reports exclude private contacts/content.
Every endpoint requires current normal site administration, has a2s statement
budget and rechecks identity/session before delivery. Unknown home-unit pointers
into legacy projects remain unchanged but are not mislabeled as organisation units.
P7 must add branch predicates before accepting unit administrators; changing only
the navigation policy would be insufficient.

Checks: `test_people_directory.py` (including500-person<200ms, ties/nulls,
filter-bound cursors and demotion during read), `test_people_profile.py` (privacy,
retained/upward-only access and denied cases), `test_people_export.py` (formula
escaping, bounds, privacy and post-commit demotion). No runtime dependency added.

## Remaining P1 work

List/profile web screens with URL filters, Record/Access/Timeline drawer and CSV
controls. Keep legacy admin endpoints working until P4. No staff edit/transfer/
status-change UI or new capability in P1.
