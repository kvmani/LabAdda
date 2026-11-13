# Personal whiteboard and home

The owner requested this feature separately from the delivery-plan packages. `/` now has a
public research-team landing page and a signed-in start page; `/login` remains a direct sign-in
route. Brand and illustrative board assets are bundled under `frontend/public/` (generated
from the approved design; values/names on the artwork are fictional). No external fonts or assets.

`/whiteboard` is an owner-private canvas, separate from shared Board rows. API routes are in
`api/personal_board.py`; ownership comes only from `current_actor`, revalidated under the existing
identity lock. No owner/workspace ID is accepted. Every save appends a `PersonalBoardRevision`
(schema 0037). Expected revisions prevent concurrent overwrite; identical immediate retries
return the saved result. Other users, administrator roles and panel sessions grant no content
access. It has no shared socket, export, search, notification or analytics content surface.

The client explicitly saves a bounded document of strokes and colored sticky notes. Notes can
be edited, dragged or positioned with keyboard/buttons. Failed saves keep drafts, conflicts require
review and saved reload confirms before discarding local changes. Reload/closing warns about
unsaved work. In-app navigation preserves drafts in memory for the current tab/session, cleared
on sign-out or identity change; private content is never cached in browser storage. Old revisions are retained, not pruned. The API
limits each document to 500 objects, 20,000 points and 250,000 encoded bytes; this is not full
storage quota enforcement. Background tab synchronization and cross-device live collaboration
are intentionally outside the private-board workflow.

Checks: `test_personal_board.py`, the real recovery integration, and `e2e/personal-board.mjs`
(root and prefix). Main regression entry: `scripts/verify.sh --e2e` with recovery enabled.

Validation: 1,540 backend tests with real recovery (zero skips), 220 frontend tests,
69 existing browser flows, 18 component-gallery checks and 24 new root/prefix browser checks
including desktop/phone axe, drag, keyboard movement and delayed-response draft retention.
Independent reviewer `pilot_review` accepted the ownership and draft-lifetime changes.
