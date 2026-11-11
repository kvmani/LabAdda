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

## Web directory and profiles

`frontend/src/features/people/` owns the read-only screen at `/admin/people`.
`usePeopleNavigation` keeps filters, paging, selected person and profile tab in the
URL. `model.peopleUrl` excludes profile parameters from reads and cursors from
reports. Server sorting covers all matching rows; the table never sorts a single
page as if it were the complete directory. Home-unit choices show full paths and
exclude projects. Calendar dates use UTC formatting without browser-zone shifts.

`usePeopleData` isolates URL/retry generations; identity changes remount the drawer.
A current 401/403 clears every metadata region. Old scopes cannot restore data.
`ExportReport` ignores completed requests after its filter scope unmounts, checks
CSV type and releases object URLs. `api.ts` preserves structured JSON errors in
binary mode. `SearchInput.value` synchronises browser navigation without replacing
the focused input. Console authority checks follow pathname changes, preserving
list and drawer focus during query-only navigation.

Record, Access and Timeline tabs use shared Drawer/Tabs controls. Appointments and
scheduled changes are explicitly pending P3/P5. Legacy account tools remain at
`/admin/people/basic`; endpoints remain working until P4. No new staff edit,
transfer or status-change UI and no new capability in P1. The help-centre framework
is still H1; the console's help link remains its honest placeholder.

`e2e/people.mjs` tests both routes: paging, URL filters/refresh, keyboard drawer
close/focus return, site-calendar dates, upward access, plain history, actual CSV
download, desktop/phone axe, member denial, late-filter responses and real authority
revocation while a success is held. Its companion fixture refuses every database
except the disposable proxy databases. The full simulation registers this suite.
`e2e/admin-console.mjs` still checks the original basic account tools and authority
boundaries. Unit tests cover URL/CSV/date boundaries, controlled search focus and
stale export denial. Run suites sequentially; proxy startup resets test data.
