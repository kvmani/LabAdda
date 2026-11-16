# Representative posting and board editing

Owner-approved scope, 16 November 2026. Status: in progress.

## Contribution rules

Reading continues to flow upward through organisation units. Whiteboards, noticeboard posts
and chat (including replies, reactions and attachments) require contribution permission.
Direct members and direct stewards contribute to their own unit. A steward of an immediate
child unit also contributes at its parent, but no higher. A child steward may delegate a
member of that child's subtree to contribute at its immediate parent. Projects and private
collaborative groups retain their direct membership rules. Personal boards and notes stay private.
Archive and read-only policies remain stronger restrictions. Site administration grants no
content privilege. Delegation never grants moderation or membership management.

A unit can appoint multiple delegates (including three, four or more); each appointment
expires or is revoked independently, in addition to automatic steward rights.
Delegation names a source child, destination parent and person; it lasts until revoked or an
optional expiry. Source stewards appoint/revoke; destination stewards may revoke. Recipients
must remain active members of the source subtree. Hierarchy moves invalidate a grant whose
source no longer has the recorded destination as parent. Existing content is retained.

## Working ledger

- [x] Inspect current policy, live delivery, board and chat entry points.
- [x] Add lossless delegation schema, policy tests and migration tests.
- [x] Enforce contribution on all shared board/chat/post mutations and live permissions.
- [x] Add delegation management and hide ineligible contribution controls.
- [ ] Improve selection, positioning and text formatting, including bundled handwritten fonts.
- [ ] Update API, help and browser coverage; run full checks and independent review.

Each verified slice is committed and pushed to main. Resume from the first unchecked item;
read the current git diff before repeating any work. Existing tasks/calendar permissions are
outside this change. Real Windows pilot acceptance remains an owner check.

### Checkpoint 1: schema foundation

Migration 0047 retains appointment history and refuses a destructive downgrade. Foundation
is the first pushed slice; the API, policy, UI and tests are prepared in the working tree for
checkpoint 2. The checked implementation items above refer to that working tree until the
next checkpoint is recorded.

Validation of the combined candidate: 1,710 backend passes, one optional recovery skip;
explicit PostgreSQL recovery separately passed with appointment preserved. Frontend lint,
types, 250 unit tests and production build pass. New root/prefix representative flow: 16
checks; existing root/prefix collaboration flow: 75/75. Different-model reviewer
`representative_final_review` accepted the corrected authorization scope after the stale
response fix. `workspaces.test.tsx` reproduces reversed responses and stale errors.

Next: push checkpoint 2 authorization code and tests, then apply and qualify the board
editing/font slice prepared outside the repository. No live Windows or office instance
has been changed. Keep the current pilot running its existing version until a backed-up
upgrade is scheduled.
