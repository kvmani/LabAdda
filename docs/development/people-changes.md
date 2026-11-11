# Reviewed staff changes

Read [P2](../plan/people.md#p2--change-protocol-add-edit-transfer),
[PO-04–12](../PEOPLE-AND-ORG.md) and [API P2](../API.md#p2-reviewed-edits-first-executable-slice).
P2 remains in progress: reviewed edits are executable; add/transfer and dialogs follow.

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
- `changes/service.py`: preview/apply orchestration and parent/per-step audits.
- `api/changes.py`: normal administrator dependency and sanitized database failures.
  `audit.record_step` preserves structured transitions without changing legacy audits.

Snapshots contain only explicitly selected staff metadata. Serialization does not
decide access. Never include credentials or private collaboration content, and
never accept executable client steps. A digest is a change detector, not authorization.

## Locking and transaction boundaries

Take the shared admin-role advisory lock, actor user/session locks, then the target
user lock. Rebuild the plan from the validated request and current state. Require
both its digest and complete revision map to match. A stale or previously applied
plan returns409; a matching blocked plan returns422. Preview writes no staff/audit
rows. Existing normal-session heartbeat maintenance remains in authentication.

Do not call `current_actor` after staging changes: its heartbeat can commit. Use
fresh locked identity/session checks; trace legacy identity/membership locks too.
Hold authority through the edit/audit commit, then revalidate realtime delivery.
Recheck authority before returning the receipt. If authority or connectivity is
lost after commit, the change may already be durable: reload before retrying.
No automatic retry or replay of an old plan. Optional contact text is never sent
externally. General settings, permissions, employment state and username cannot be
edited through the staff-field route.

## Checks and next slices

`test_change_plan.py` proves immutable snapshots, canonical bytes, digest binding,
order and invalid values. `test_changes_edit.py` proves reload persistence, no-op
and uniqueness blockers, stale/tampered confirmations, concurrent apply-once,
rollback on final audit failure, structured audits, denied users/panels/readers,
no content, sanitized failures and authority loss before/after commit.

Next: add-person activation slips; transfers, bounded gained/lost access and open
assignment counts, steward notices and dated handover expiry; dialogs and browser
qualification at root/prefix; final independent review before marking P2 done.
Keep the old admin routes until P4. Retain races with legacy writes in qualification.
