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

Next: an edit dialog; handover period (needs dated membership expiry, P5's scheduler);
independent review before marking P2 done.
Keep the old admin routes until P4. Retain races with legacy writes in qualification.
