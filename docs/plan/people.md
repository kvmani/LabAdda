# Track P — people and organisation management

Contract: [PEOPLE-AND-ORG.md](../PEOPLE-AND-ORG.md) (PO-01–PO-25). Interaction rules:
[ui-design-system.md](../development/ui-design-system.md) UX-07, UX-11.

Rules for the whole track:

- **Every package P1–P7 needs independent review** before it is marked done.
- Administrators and unit administrators never receive content. Each package adds the
  "no content in responses" test described in [track A](admin.md).
- All membership writes go through `memberships.py`; all changes commit in one transaction with
  audit rows; the realtime hub is revalidated after commit, exactly as `api/admin.py` does today.
- Keep the existing `/admin/users`, `/admin/workspaces` and membership endpoints working until
  P4 is done, then remove them and their screens in one commit.

## Scenario

Use this fictional story for tests, browser checks and help screenshots. Extend
`backend/labadda/fixtures.py` only as far as each package needs.

*Surface Science Division* (Head: Dana) has sections *Thin Films* (steward Asha; members Ben,
Fay-disabled) and *Catalysis* (member Chen). In one month: (1) Dana retires; Asha is made
**acting Head** of the division for 60 days; (2) Ben transfers from Thin Films to Catalysis with
a 7-day handover; (3) Chen is promoted and becomes steward of Catalysis; (4) twelve new joiners
arrive by spreadsheet; (5) a new section *Sensors* is split from Thin Films; (6) later, Thin
Films is merged into Sensors.

### P1 · Staff record, people list and profile

**Status: done (2026-11-11).** Staff foundation, protected reads, URL directory,
Record/Access/Timeline drawer and audited CSV download qualified at root and prefix. [Guide](../development/people.md).

Size M. Depends on A1, Q1.

**Goal.** PO-01, PO-02, PO-03, PO-20: the staff record exists and administrators can find and
read people.

**Build.** Migration: add to `users` — `employee_no` (nullable, unique), `designation`,
`contact_email`, `contact_phone`, `status` (check constraint over the PO-02 values, backfilled:
active accounts → `active`, pending activation → `invited`, disabled → `left`),
`status_effective_on`, `expected_return_on`, `joined_on`, `last_seen_on` (date only),
`revision` (default 1). Keep `is_active` and set it from `status` in one helper,
`people.set_status(...)`, used everywhere. New `backend/labadda/people.py` (domain) and
`api/people.py`: `GET /admin/people` (search over name, username, employee number; filters
status, unit including sub-units, role; sort; cursor pagination), `GET /admin/people/{id}`,
`GET /admin/people/{id}/timeline` (from audit rows where the person is target). Frontend
`features/people/`: list with filters in the URL, profile `Drawer` with tabs Record · Access ·
Timeline, CSV export.

**Acceptance.** Backfill test on a database populated at the previous migration. Search and
filter tests with 500 generated people stay under 200 ms. `last_seen_on` stores a date, never a
time. Member → 403; panel → 401. Timeline shows existing audit history in plain sentences.

**Not in this package.** Any change to people (P2).

### P2 · Change protocol; add, edit, transfer

**Status: in progress (2026-11-11).** Immutable metadata snapshots and deterministic,
versioned plan/digest primitives implemented. No change endpoints or dialogs yet.

Size L. Depends on P1.

**Goal.** PO-04–PO-12: the preview/apply protocol and the first three change kinds.

**Build.** `backend/labadda/changes/`: `plan.py` (dataclasses `Step`, `Warning`, `Blocker`,
`Plan`; canonical JSON serialisation; SHA-256 digest over the canonical form), `guards.py`
(PO-08, each guard a small function returning blockers or warnings), `kinds/add_person.py`,
`kinds/edit_person.py`, `kinds/transfer.py` (each exposes `build(db, request) -> Plan` and
`apply(db, actor, plan)`), `service.py` (`preview`, `apply`: take `lock_admin_roles` and the
identity locks in a fixed order, rebuild the plan, compare digest and revisions, apply steps,
write the parent and per-step audit rows, commit, revalidate the hub). API
`POST /admin/changes/preview` and `/apply` with a discriminated union on `kind`. Transfer
computes inherited access gained and lost with `policy`, and the open-assignment **counts** per
workspace; after commit it creates an in-app notice for the stewards of those workspaces
(reuse `notify.create`; the notice text names the person and the count only). Frontend: `Stepper`
dialogs "Add person" (ends on the printable activation slip) and "Transfer" (choose unit and
role → options → review with before/after, warnings and required reason → done), launched from
the people list and profile.

**Acceptance.** Tests: stale digest → 409 and nothing written; concurrent apply of two plans on
the same person → one succeeds, one 409; every blocker and warning; atomicity (inject a failure
in the last step and assert no row changed); audit parent + steps; after transfer Ben's socket
subscription to Thin Films is revoked and a delayed fetch returns 404; stewards notified,
administrator response contains counts only. Browser suite plays scenario step 2 by buttons and
keyboard only.

**Not in this package.** Future-dated changes (P5), positions (P3), drag and drop (P4).

### P3 · Positions, authority, leave, retirement, suspension

Size L. Depends on P2.

**Goal.** PO-13–PO-18.

**Build.** Migration `unit_positions (id, workspace_id, user_id, position head|deputy, acting,
starts_on, ends_on, revert_role member|steward|none, ended_at, created_by)` with a partial
unique index for one current Head per unit. Change kinds: `promote`, `change_authority`,
`additional_charge`, `leave`, `return`, `retire`, `suspend`, `reinstate`, each in its own module
under `changes/kinds/`. Scheduler step `positions.expire_due(now)` ends acting appointments and
dated additional charges and applies `revert_role` (idempotent; raises an attention item).
Retirement plan lists last-steward workspaces and requires a successor for groups and projects
(choose among member names only). Frontend dialogs for each kind sharing one review step
component; positions shown on the profile and unit panel.

**Acceptance.** Scenario steps 1 and 3 pass as backend and browser tests. Acting appointment
expires on its date under an injected clock and reverts the role. Retiring the last
administrator is blocked. Retiring a group's last steward without a successor is blocked.
Suspended and retired users cannot sign in and their sessions and sockets end at once.
Reinstate issues a new activation code and restores no access by itself.

### P4 · Organisation chart and unit changes

Size L. Depends on P2.

**Goal.** PO-19, PO-21: graphical organisation management.

**Build.** Migration: `workspaces.code` (unique for `org` units, backfilled from the name).
Change kinds `unit_create`, `unit_rename`, `unit_move`, `unit_merge`, `unit_split`,
`unit_close`, `unit_reopen`. `GET /admin/org/tree`. Frontend `features/org/`: `OrgChart`
(tree layout computed in a pure, unit-tested function; SVG connectors; collapse, search-and-
reveal, zoom, fit), unit side panel (Head, stewards, people, sub-units, actions), drag a person
onto a unit → opens the Transfer review; drag a unit → opens the Move review; identical
"Move to…" / "Transfer…" menu actions. A side list of projects and groups (names, steward
names, counts). Then delete the old basic admin people/organisation screens and endpoints.

**Acceptance.** Scenario steps 5 and 6. Moving a unit under its own descendant is blocked.
Move preview lists access gained and lost as counts; after apply, a member of the moved branch
loses and gains exactly those ancestor reads (verified through real read requests). Merge keeps
history readable to former members and archives the source. Chart renders 300 units and 2 000
people smoothly (layout under 100 ms; test). Full keyboard path in the browser suite; axe clean.

### P5 · Scheduled changes and attention list

Size M. Depends on P3, P4.

**Goal.** PO-06, PO-22.

**Build.** Migration `scheduled_changes (id, kind, request JSON, plan_digest, effective_on,
state pending|applied|cancelled|needs_review, created_by, reason, applied_at, note)`.
`effective_on` accepted by preview/apply; scheduler step `changes.run_due(now)` (site time
zone, start of day) re-previews and applies or marks `needs_review` and raises an event.
`GET /admin/changes/scheduled`, cancel. `GET /admin/org/attention` implementing every PO-22
item as one bounded query each. Frontend: scheduled list on People overview and on profiles;
attention list with a fix link per item.

**Acceptance.** Injected-clock tests: applies on the day; a conflicting change made in between
→ `needs_review`, nothing applied; cancelling works; the scheduler step is idempotent when run
twice. Each attention item has a test that creates and then clears it.

### P6 · Staff list import and bulk changes

Size M. Depends on P3.

**Goal.** PO-23.

**Build.** `changes/importer.py`: strict CSV parsing with the standard library (`csv`), UTF-8
with BOM tolerated, header validation, per-row errors with line numbers, limits. Dry-run report
with a digest; apply builds one `bulk` change from the selected rows through the P2 service.
Template download. Frontend: upload → report table grouped Add / Change / Transfer / Absent /
Errors with select-all per group → review → apply → activation slips for new people as one
printable page. Multi-select bulk transfer and status change on the people list (≤ 100).

**Acceptance.** Scenario step 4. Formula-like cells are treated as text. A file with one bad
row applies nothing unless that row is unselected. People absent from the file are never
changed. Oversized or non-CSV upload rejected before parsing. The upload is not stored.

### P7 · Unit administrators

Size M. Depends on P4.

**Goal.** PO-24.

**Build.** Migration `unit_admin_grants (user_id, workspace_id, granted_by, granted_at,
revoked_at)`. `policy.people_scope(db, user)` returns the set of unit IDs a person may
administer (all for site administrators). Apply it in list, profile, preview and apply (a plan
touching anything outside the scope is blocked). Site-administrator-only appoint/revoke with
audit. Console navigation shows only People and Organisation to unit administrators, filtered
to their branch.

**Acceptance.** Matrix test: unit administrator of division X can transfer within X; cannot
see or change people in sibling division Y; cannot transfer X→Y alone; cannot grant
administrator; gains no content access (existing content denial tests re-run as this user).

### P8 · My profile and sessions

Size S. Depends on U2. No independent review needed beyond the checklist, except the password
endpoint, which follows the patterns in `api/auth.py`.

**Goal.** PO-25.

**Build.** `GET /me/profile`, `POST /me/password` (current password required, rate limited,
revokes other sessions), `GET /me/sessions`, `DELETE /me/sessions/{id}` (never returns session
tokens; shows start time, last seen, browser family parsed from a stored short label).
Frontend `/profile` page: record (read-only), access list, password form, sessions. Add
"My profile" as the first item of the account menu in `frontend/src/features/shell/TopBar.tsx`.

**Acceptance.** Wrong current password is rate limited and audited; other sessions end
immediately (socket closed); a user cannot see or end another person's session (404).
