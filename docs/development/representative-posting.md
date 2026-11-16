# Representative posting and board editing

Owner-approved scope, 16 November 2026. Status: complete; code and documentation are ready for a backed-up pilot upgrade.

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
- [x] Improve selection, positioning and text formatting, including bundled handwritten fonts.
- [x] Update API, help and browser coverage; run full checks and independent review.

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

### Checkpoint 2: representative policy and management

Authorization slice ready to push: HTTP and both socket permission paths, multi-person
appointments, revocation/expiry and permanent invalidation, audited authority changes,
author/current-steward board mutations including undo, panel isolation, hidden controls and
stale-response guards. API, specification and in-app help updated. Independent different-model
reviewer `representative_final_review` (GPT-6 Astra) found no remaining authorization findings
after fixes. Backend 1,710 passed/one optional skip; explicit real recovery passed; frontend
250 passed plus lint/types/build; existing browser 75/75 and new representative browser 16/16.
Additional demoted-steward undo regression passed after the full run.

Remaining board slice: bundled fonts and server image rendering, selection/dragging and
keyboard movement/edit controls on shared and private boards, font/size persistence and
validation, tests/help/browser checks. Prepared and separately tested in
`/tmp/labadda-board-validation` (baseline originals `/tmp/labadda-board-base`); apply only
changed source/assets after comparing against the baseline, never copy temporary proxy or
configuration files. Final combined `scripts/verify.sh --e2e` is still required.

### Checkpoint 3: board editing qualification

Authorization is on main at `bdafb28` (schema foundation `d47f406`). Applied the separately
validated selection, keyboard movement and font slice. New files: `board_fonts.py`, bundled
font assets/licences, `textStyle.ts`, `TextStyleFields.tsx`, `SelectedObjectControls.tsx` and
personal `move.ts`. JSON carries allowlisted `font_family` and `font_size`; no new migration
or runtime dependency. Sticky editor effects now retain typed drafts across parent redraws.
Temporary validation passed 14 style backend tests, 19 private/board regressions and both
root/prefix style browser flows. Final root checkout checks are pending. Next: finish tests,
help/API and combined verification, then commit/push this slice and mark this ledger complete.

### Final checkpoint: complete

- `scripts/verify.sh --e2e` passed: 1,725 backend tests, one optional recovery skip,
  migration drift, frontend gates, root/prefix flows (75) and component gallery (18).
- After the final chat reading/summary UI corrections, frontend lint, types, **257 unit
  tests** and production build passed. Different-model reviewer `representative_final_review`
  accepted the corrected menu and destination handling with no remaining findings.
- Fresh root/prefix browsers: representative permissions **26**, board editing/fonts **24**,
  existing private-board workflow **22**. Desktop/mobile accessibility passed. Font/editor
  flow made no external requests. Private isolation and draft preservation still pass.
- Separately enabled real PostgreSQL recovery passed with representative appointments and
  handwritten private-board formatting preserved. Each concurrent test run used a distinct
  disposable database.

Selection supports drag movement and keyboard controls, including drawings and images.
Notes/text have four local fonts and bounded sizes. Owner/current-steward checks still govern
shared edits. Permission loss hides editor save actions and retains the draft for copying.
Readers retain thread and task actions; posting a copied summary names an eligible destination
and requires confirmation when changing audience. No new runtime dependency or config variable.

The whole requested scope is complete. Next action belongs to the pilot operator: back up the
running database and assets together, stop the app, update code/build frontend, apply migration
0047 and restart. Preserve Windows-specific local setup when replacing a ZIP installation.
No Windows PC or office server was upgraded by these cloud tests. Office pilot acceptance and
colleague feedback remain separate from these synthetic checks.
