# People and organisation management — contract

Status: **normative for v1.0; not yet implemented** except where "Exists today" says so.
Delivered by track P of [the plan](plan/people.md). Summarised in
[SPECIFICATIONS.md S9](../SPECIFICATIONS.md). Builds on S2 (identity and permissions) and never
weakens it.

**Purpose.** A real organisation changes constantly: people join, move between sections, get
promoted, take charge of a unit, go on long leave, retire or leave; units are created, renamed,
moved, merged and closed. An administrator with no technical background must be able to make
each of these changes correctly, in a few clicks, on a graphical screen — seeing the
consequences before anything is written, and being able to explain later who changed what and why.

## Exists today

Create account with one-time activation code; enable/disable; reset; grant or remove a
membership (member or steward); create a unit or project; move a unit (API only); archive;
last-administrator and last-steward protection; audit rows for these actions; live revocation
of sessions and subscriptions when access changes. Source: `backend/labadda/api/admin.py`,
`memberships.py`, `frontend/src/pages/Admin.tsx`.

## Terms

| Term | Meaning |
| --- | --- |
| Person | A user account plus its staff record |
| Unit | An organisation workspace (`kind = org`): root, group, division, section … any depth |
| Home unit | The one unit a person belongs to. Stored in `users.home_workspace_id` |
| Access | A membership (member or steward) in a unit, project or collaborative group |
| Position | A named responsibility in a unit: **Head** or **Deputy**, optionally *acting* until a date. A position holder is always a steward of that unit while the position is current |
| Change | One reviewed operation on people or units (transfer, retirement, unit move …) |
| Plan | The server-computed list of exact steps and consequences of a change, shown for review |

## Staff record

**PO-01.** Each person has: username (immutable), display name, employee number (optional,
unique when present), designation (free text, e.g. "Scientific Officer E"), work e-mail and
phone extension (optional contact text; nothing is sent to them), home unit, employment status,
status effective date, expected return date (for leave), date joined, and an integer revision.
No free-text notes field: remarks belong in the reason of a change.

**PO-02.** Employment status and its effect on sign-in:

| Status | Meaning | Can sign in |
| --- | --- | --- |
| `invited` | Account created, activation not completed | Only to activate |
| `active` | Working normally | Yes |
| `on_leave` | Long leave or deputation; keeps access unless the change says otherwise | Yes by default; the change may block it |
| `suspended` | Access stopped immediately by an administrator | No |
| `retired` | Retired from the organisation | No |
| `left` | Resigned, transferred out of the organisation, or otherwise departed | No |

`users.is_active` remains the single switch the rest of the system checks; it is derived from
status in the same transaction. Deactivating always revokes sessions and live subscriptions.

**PO-03.** A person's content is never removed or re-attributed by any change. Posts, messages,
board strokes and task history keep the author's immutable ID and show their current display
name. A departed person's personal notes and personal task lists are retained and inaccessible
to everyone, including administrators.

## The change protocol (applies to every change below)

**PO-04. Preview, then apply.** Every change is two calls. *Preview* validates the request and
returns a plan: ordered steps (each a plain sentence plus structured before/after), warnings,
blocking problems, the count of people whose access changes, and a digest. *Apply* sends the
same request with the digest, the record revisions and a reason. The server recomputes the plan
under lock; if the digest differs it returns `409 plan_stale` and writes nothing. A plan with a
blocking problem cannot be applied. Preview never writes.

**PO-05. Atomic and audited.** Apply runs in one transaction: all steps or none. It writes one
audit event for the change (actor, kind, reason, effective date, plan digest) and one per step
(target person or unit, before, after). Realtime revalidation is sent after commit.

**PO-06. Effective date.** A change takes effect now or at the start of a chosen future day in
the site time zone. Future changes are stored as *scheduled changes*, listed on screen, and can
be edited (by cancelling and re-creating) or cancelled until they run. When the day arrives the
scheduler recomputes the plan: if it still matches, it is applied and attributed to the
administrator who scheduled it; if not, it is marked **needs review**, nothing is applied, and
an attention item is raised. Back-dated changes are not supported; the record states the real
date in the reason.

**PO-07. No content access.** Plans, warnings and reports for administrators contain names,
units, roles, dates and counts only. Where a change affects work inside a workspace (for
example open tasks assigned to someone leaving), the administrator sees a count, and the
stewards of that workspace — who already have access — receive an in-app notice telling them
to reassign.

**PO-08. Guards that every plan checks.**

- At least one active administrator remains.
- A unit is not left without an active steward unless the administrator ticks an explicit
  acknowledgement; a collaborative group or project is never left without an active steward
  while it has other active members — a successor from its members must be chosen.
  Suspension, and leave with sign-in blocked, take effect at once and only warn when the person
  is a group's or project's last active steward (owner decision 2026-11-12).
- A position holder is active and has a home or membership in that unit.
- Usernames and employee numbers stay unique; the tree stays a single-rooted tree without cycles.
- The actor is allowed to act on every person and unit in the plan (PO-21).

**PO-09. Undo.** A change is undone by a new, opposite change, offered as "Reverse this change"
on the timeline for 7 days when the opposite change is still valid. It goes through the same
preview and audit. There is no silent rollback, and a deactivated person who is reactivated
always gets a fresh activation code.

## People changes

**PO-10. Add a person.** Name, username, optional staff fields, home unit, role in that unit,
start date. Result: account in `invited` status, membership in the home unit, and a one-time
activation code shown once with a printable slip (name, username, code, expiry, sign-in
address). The same employee number blocks the plan (PO-08); a very similar name warns.

**PO-11. Edit a record.** Display name, designation, employee number, contact fields. No access
change. A display-name change is audited with before and after.

**PO-12. Transfer.** Move a person from home unit A to unit B. The plan sets the home unit to
B, adds a membership in B with the chosen role, and — by default — removes the membership in A
and ends any position held in A. Options: keep access to A until a date ("handover period");
keep A as additional access. Memberships in projects and collaborative groups are listed and
kept unless individually unticked. Warnings: A left without a steward or head; inherited access
gained and lost (which ancestor units the person can newly read or no longer read); number of
open shared tasks assigned to the person in units they will no longer see.

**PO-13. Promotion or change of designation.** Change designation, and optionally role
(member ↔ steward) or position in a unit. The plan states clearly whether access or moderation
powers change.

**PO-14. Change of authority.** Replace the Head or Deputy of a unit. Choose the successor
(must be, or in the same plan become, a member of the unit) and what happens to the outgoing
holder: stays as member, stays as steward, is transferred, or retires. The successor becomes
steward. **Acting appointments** have an end date; on that date the position ends
automatically, the role returns to what the plan recorded, and an attention item asks for a
permanent decision. One current Head per unit.

**PO-15. Additional charge.** Give a person access (member or steward, optionally a position)
in a second unit, with an optional end date after which it is removed automatically.

**PO-16. Leave and return.** Set `on_leave` with an expected return date; optionally block
sign-in; optionally appoint an acting replacement for each position held (PO-14). Return sets
`active` and ends acting appointments made for the absence. An overdue return date raises an
attention item; it never changes access by itself.

**PO-17. Retire or leave.** Choose status (`retired` or `left`) and last working day. The plan:
ends every position (successor or acknowledgement required per PO-08), keeps or removes each
membership (default: remove), deactivates the account at the effective time and revokes
sessions. It lists workspaces where the person is the last steward and requires a successor for
each group or project. It shows counts of open shared tasks assigned to the person per
workspace and notifies those workspaces' stewards.

**PO-18. Suspend and reinstate.** Suspend takes effect immediately with a required reason.
Reinstate returns a person from `suspended`, `retired` or `left` to `invited` with a new
activation code. Previous access is **not** restored automatically; the plan offers the
person's last placement from history as a starting point to review.

## Organisation changes

**PO-19.** Every unit has a display name and a short unique **code** (e.g. `SSD-TF`) used in
imports and shown on the chart. Supported changes, each with preview and audit:

| Change | Plan must show |
| --- | --- |
| Create unit | Parent, code, optional Head |
| Rename / recode | Before and after; links keep working because IDs do not change |
| Move unit (with its sub-units) | New parent; for members of the moved branch, which ancestor units they newly can and no longer can read; counts only |
| Merge unit A into B | People whose home is A get home B and a membership in B; A is archived read-only and existing members keep read access to A's history; positions in A end |
| Split | Create the new unit, then transfer selected people in the same plan |
| Close unit | Refused while any person's home is the unit or an active sub-unit exists; otherwise archive |
| Reopen | Unarchive |

Units are never deleted. The root cannot be moved, merged or closed.

## Viewing and finding

**PO-20. People list and profile.** A searchable, sortable, filterable, paginated list
(name, username, employee number, designation, home unit, status, last sign-in date). A person's
profile shows the staff record, all access with role and how it was obtained, positions,
scheduled changes, and a **timeline** of every change with actor, date and reason. Sign-in
history shows dates only. Lists export to CSV with spreadsheet-formula escaping; each export is
audited.

**PO-21. Organisation chart.** A graphical, collapsible chart of units showing code, name, Head,
and counts of people. Selecting a unit lists its people and positions. Search finds units and
people and reveals them in the chart. People and units can be dragged to propose a transfer or
a move; the same actions exist as buttons and menu items; nothing is written before the review
step ([UX-11](development/ui-design-system.md)). Projects and collaborative groups are listed
beside the chart (name, steward names, member count) and are not part of the tree.

**PO-22. Attention list.** The People overview lists, with a one-click route to the fix: units
without an active steward or Head; people without a home unit; activation codes pending more
than 14 days; acting appointments ending within 14 days or expired; overdue returns from leave;
scheduled changes needing review; groups or projects whose only steward is inactive; accounts
never signed in after 90 days.

## Bulk changes

**PO-23. Import from a spreadsheet.** Upload a CSV (UTF-8; a template with one example row can
be downloaded) with columns `employee_no, username, display_name, designation, unit_code, role,
status, effective_on`. The server returns a dry-run report: rows to add, rows to change (field
by field), transfers, people in the system but absent from the file (listed for information,
**never** changed automatically), and row errors with line numbers. The administrator selects
which valid rows to apply; the selection is applied as one atomic change with one reason. Limits:
2 000 rows, 1 MiB. The file is parsed in memory and not stored. Multi-select on the people list
offers the same bulk transfer and bulk status change for up to 100 people.

**PO-23a. Import staff from Excel.** An administrator can onboard a laboratory from one `.xlsx`
(or CSV) workbook with columns `full_name, division, section, Emp No, email, Extension, Group,
Residence Phone, username, Password, is_active` and an optional `role`. The hierarchy is
Organisation, Group, Division, Section, person; each unit records its level. **Group is
mandatory; division and section are optional and never defaulted**: a person belongs to the
deepest unit named, and a section with no division sits directly under the group. Missing units
are created (matched by name, case-insensitively, within the same parent), the e-mail must be
`<username>@<site e-mail domain>`, and the whole file is reviewed first and applied all or
nothing through the PO-23 protocol. A given password is hashed at once, is never stored anywhere
else, and must be changed at first sign-in; `role: admin` makes a site administrator and is
audited. See [the guide](development/people-changes.md#excel-staff-import-p6x).

## Who may do this

**PO-24. Capabilities.** Site administrators can make every change. A site administrator may
appoint a **unit administrator** for a unit: that person can add people, edit records, transfer,
change roles and positions for people whose home is in that unit's branch, and manage units
inside the branch. A transfer into or out of the branch needs a site administrator or unit
administrators of both branches. Unit administrators cannot create administrators, cannot see
other branches' people beyond the directory, and — like site administrators — gain no content
access. Appointments are audited, listed, and revocable. Board-only sessions are refused.

## Self-service

**PO-25.** A signed-in person can: view their own record and access; change their password
(current password required; other sessions are signed out); see their active sessions with
start time and browser family, and sign out the others; choose their home view among units they
belong to; choose the colour theme. They cannot edit their staff fields.

## Interfaces (summary — full shapes go in docs/API.md with each package)

```text
GET    /admin/people                       list, search, filter, paginate
GET    /admin/people/{id}                  record, access, positions, scheduled changes
GET    /admin/people/{id}/timeline         audit-derived history
POST   /admin/changes/preview              { kind, ... }  -> plan + digest
POST   /admin/changes/apply                { kind, ..., digest, revisions, reason }
GET    /admin/changes/scheduled            list;  DELETE /admin/changes/scheduled/{id}
GET    /admin/org/tree                     units with code, head, counts
GET    /admin/org/attention                attention list (PO-22)
POST   /admin/people/import/preview        multipart CSV -> dry-run report
POST   /admin/people/import/apply          { report_digest, selected_rows, reason }
GET    /me/profile   POST /me/password   GET /me/sessions   DELETE /me/sessions/{id}
```

`kind` is one of `add_person, edit_person, transfer, promote, change_authority,
additional_charge, leave, return, retire, suspend, reinstate, unit_create, unit_rename,
unit_move, unit_merge, unit_split, unit_close, unit_reopen, bulk`.

## Acceptance

Tests T53–T60 in [TESTING.md](../TESTING.md) are release gates. The fictional scenario used
throughout is in [the plan](plan/people.md#scenario): a retirement of a division head with an
acting successor, a transfer between sibling sections, a promotion to steward, a merge of two
sections, and an import of twelve joiners.

## Open decisions for the owner

1. Should ordinary users see colleagues' designation and home unit in the colleague directory?
   S2.1 currently limits the directory to display name and username. Default: **no change**.
2. Should `on_leave` block sign-in by default? Default: **no**.
3. Handover period default for transfers. Default: **none** (access to the old unit ends at once).
