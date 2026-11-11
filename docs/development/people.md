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

## Remaining P1 work

Read-only paginated/filterable people API, protected staff profile/access/timeline,
formula-safe audited CSV and list/profile web screens. Keep legacy admin endpoints
working until P4. No staff edit/transfer/status-change UI or new capability in P1.
