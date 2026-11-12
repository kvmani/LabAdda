# Reviewed staff changes

Read [P2](../plan/people.md#p2--change-protocol-add-edit-transfer),
[PO-04–12](../PEOPLE-AND-ORG.md) and [API P2](../API.md#p2-reviewed-edits-first-executable-slice).
Edit, add-person and transfer kinds are executable; "Add person" and "Transfer" dialogs
are on the people console. Edits have no dialog yet; handover periods are deferred.

## Minimal paths

- `changes/plan.py`: Step/Warning/Blocker/Plan, immutable Snapshot, version1 canonical
  JSON and SHA-256. Inputs and response copies cannot mutate stored snapshots.
  Actor, normalized request, revisions, ordered consequences and counts bind the digest.
- `changes/requests.py`: bounded staff-field allowlist, explicit null versus omitted,
  trimmed values, valid single-line Unicode, forbidden unknown keys and apply evidence.
- `changes/guards.py`: metadata-only uniqueness guard; extend with relevant PO-08
  checks as kinds are added. Edits change no authority, membership or tree state.
- `changes/kinds/edit_person.py`: current record, exact before/after, duplicate/no-op
  blockers; executor applies only the server-built whitelist and increments revision.
- `changes/kinds/add_person.py`: invited non-admin account, home membership through
  `memberships.set_membership`, `credentials.issue_credential`; the code is only in the
  receipt. Plan steps name `new:<username>`; `record_plan` audits the real identity.
  Similar names (casefolded, word-sorted, ratio ≥0.88) warn; uniqueness blocks.
- `changes/kinds/transfer.py`: proposed grants = current minus old home (unless kept)
  minus listed projects/groups plus the new unit; `policy.readable_from_grants` gives
  access gained/lost; open shared task counts per lost workspace; PO-08 steward guards;
  steward notices (`notify.create`, kind `reassign`, source `transfer`) in the same
  transaction. `api/notifications.py` renders them with the person's name and a live
  count, and hides them once the steward cannot read the workspace.
- Every kind exposes `build(db, request, actor_id, settings)` and
  `apply(db, actor, plan, request, settings, reason) -> (person, receipt extras)`;
  `service.KINDS` dispatches. Frontend: `features/people/useChangeReview.ts`,
  `PlanReview.tsx`, `AddPersonDialog.tsx`, `ActivationSlip.tsx`, `TransferDialog.tsx`.
- `changes/service.py`: preview/apply orchestration and parent/per-step audits.
- `credentials.py`: shared one-time activation/reset issuer used by legacy tools
  and future onboarding. `people.USERNAME_RE` is the shared identity spelling rule.
- `api/changes.py`: normal administrator dependency and sanitized database failures.
  `audit.record_step` preserves structured transitions without changing legacy audits.

Snapshots contain only explicitly selected staff metadata. Serialization does not
decide access. Never include credentials or private collaboration content, and
never accept executable client steps. A digest is a change detector, not authorization.

## Positions and P3 kinds

- `positions.py`: the `unit_positions` domain (current rows, `appoint`, `end`, `revert`,
  `expire_due`, `expiry_job` in the scheduler tuple, `positions_by_person` for the directory
  and profile). `memberships.set_membership`/`remove_membership` end a holder's Head/Deputy
  row when they stop being a steward, so legacy writes cannot break the invariant.
- `changes/actions.py`: `Draft` (person, ordered `Action`s = step + write, warnings,
  blockers) and the shared actions `set_role`, `end_position`, `appoint`, `set_status`
  (deactivation revokes sessions). P3 kinds build a draft; `build` returns its plan and
  `apply` rebuilds the same draft under lock and runs it. Each kind also exposes `lock_scope`.
- `changes/kinds/common.py`: loading, `lock_person_scope` (every granted or held workspace,
  sorted), `future_date`, open-task counts and `notify_stewards` (shared with transfer).
- `changes/guards.py`: `last_administrator`, `not_self`, `position_holder`,
  `group_successor`, `active_stewards`, `steward_gap`.
- Kinds: `promote`, `change_authority`, `additional_charge`, `leave`, `return_from_leave`
  (kind `return`), `retire` (and `left`), `suspend`, `reinstate`. One current Head per unit
  plus one acting Head while the Head is away (`covers_id`); `return` ends those covers.
- Attention items are not built here: expiry writes `position.expire` and keeps the ended
  acting row; P5's attention list reads them.

## Locking and transaction boundaries

Take the shared admin-role advisory lock, actor user/session locks, then (transfer)
the workspace role locks of every unit/group in scope in sorted order, then the target
user lock. Onboarding locks the home unit's roles; uniqueness races end in409.
The 2s statement timeout covers only the authority lock waits and is restored before
the change is built and written. A transfer whose home unit moved before the row lock
is stale (409) without rebuilding. Rebuild the plan from the validated request and current state. Require
both its digest and complete revision map to match. A stale or previously applied
plan returns409; a matching blocked plan returns422. Preview writes no staff/audit
rows. Existing normal-session heartbeat maintenance remains in authentication.

Do not call `current_actor` after staging changes: its heartbeat can commit. Use
fresh locked identity/session checks; trace legacy identity/membership locks too.
Hold authority through the edit/audit commit, then revalidate realtime delivery.
The receipt is returned after commit without a further authority check, so a
one-time code is never lost to a session ending mid-request. If connectivity is lost
after commit, reload before retrying; `changes/activation.py` issues a fresh code.
Reissue and `/auth/activate` lock the account row before its tokens, so a code is
never left live on an activated account. Reissue, like the legacy reset, also serves an
invited administrator account (one created by the old account tools).
No automatic retry or replay of an old plan. Optional contact text is never sent
externally. General settings, permissions, employment state and username cannot be
edited through the staff-field route.

## Checks and next slices

`test_change_plan.py` proves immutable snapshots, canonical bytes, digest binding,
order and invalid values. `test_changes_edit.py` proves reload persistence, no-op
and uniqueness blockers, stale/tampered confirmations, concurrent apply-once,
rollback on final audit failure, structured audits, denied users/panels/readers,
no content, sanitized failures and authority loss before/after commit.

`test_changes_add.py` and `test_changes_transfer.py` cover onboarding and T55:
memberships, socket revocation with delayed404, gained/lost equal to real reads,
steward notices, guards, stale/concurrent/atomic apply and denial. Browser:
`e2e/people-changes.mjs` (keyboard add, slip activation, Ben's transfer, axe).

`test_changes_authority.py`, `test_changes_departure.py` and
`test_positions_migration.py` cover T56 and scenario steps 1 and 3 (injected-clock expiry,
stale/concurrent/atomic apply, audits, T61, denial). Browser: `e2e/people-authority.mjs`.

Next: an edit dialog; handover period (P5's scheduler can now reuse dated rows);
future-dated retirement (P5).
Keep the old admin routes until P4. Retain races with legacy writes in qualification.

## Unit kinds (P4)

- `changes/unit_requests.py` holds the seven unit request models (`unit_create`, `unit_rename`,
  `unit_move`, `unit_merge`, `unit_split`, `unit_close`, `unit_reopen`); `changes/text.py` is the
  shared single-line text rule. Codes are upper-cased once, in the request.
- `changes/kinds/unit_common.py`: `UnitDraft` (the unit counterpart of `Draft`: no person, empty
  `revisions`, and a `box` that lets later steps reach a unit created earlier in the same plan),
  `access_counts` (who gains or loses reads when parents change; counts only), the create/join/
  home actions used by create and split, and the shared blockers (`root_fixed`, `open_unit`,
  `code_taken`). Merge, split and close reuse `set_role`, `end_position` from `actions.py`.
- `service.py` treats a `Workspace` returned by `apply` as the subject: the parent audit row has
  `scope_type:"workspace"`, the receipt carries `unit_id`, and the hub revalidates every socket.
- A unit has no revision counter; the digest over its before/after state is the stale guard.
- Merge keeps the source's memberships, so former members still read its history after it is
  archived; it never gives stewardship in the target.
- Chart data: `org_tree.py` and `api/org.py` (`GET /admin/org/tree`). Tests: `test_changes_units.py`,
  `test_org_tree.py`, `test_unit_codes_migration.py`.
- Chart UI: `frontend/src/features/org/` (`layout.ts` is the pure, unit-tested tree layout;
  `OrgChart.tsx` draws SVG; `useDrag.ts` turns a drop of a person or unit onto a unit into the
  Transfer or Move review, never a write; `UnitDialogs.tsx` reuses `ChangeDialog`). The basic
  project tools stay at `/admin/org/basic` until projects get their own screen. Browser check:
  `e2e/org-chart.mjs` (keyboard path, split and merge, gestures, real reads, axe, root and prefix).

## Staff list import and bulk changes (P6)

- `changes/importer.py`: pure parser (standard `csv`, UTF-8 with BOM, strict header, 1 MiB,
  2 000 rows, 200-character cells). Per-row problems carry the line number; file-level problems
  raise `Invalid`/`UploadTooLarge` before any row is read. Formula-like cells stay literal text.
- `changes/import_report.py`: matches rows to people by username and units by `unit_code`, makes
  ordinary `add_person`/`edit_person`/`transfer`/`suspend` requests and asks each kind's own
  `build` for warnings and blockers, so a blocked row becomes an error row with no request.
- `changes/bulk.py`: `BulkPreview`/`BulkApply`. The digest hashes the ordered per-request plan
  digests; apply locks every target, rebuilds, compares, then applies each kind and
  `record_plan`s it in one transaction. A client never sends steps.
- `api/changes.py`: `/import/template`, `/import/preview` (raw `text/csv` body streamed with a
  size cap), `/bulk/preview`, `/bulk/apply`. Tests: `test_import_parser.py`,
  `test_changes_import.py`.
  Browser check: `e2e/people-import.mjs` (upload, report, selection, slips, bulk suspend, member 403).
