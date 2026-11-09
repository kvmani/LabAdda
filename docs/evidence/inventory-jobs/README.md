# Inventory job browser evidence

Synthetic local validation on 2026-11-09. `e2e/inventory-jobs-fixture.py` is restricted
to the two disposable proxy-stack databases and prepares queued, retried,
expired-lease and cancelled jobs through the real job service. Its retry includes
a failed missing-root scan followed by a completed observation.

`e2e/inventory-jobs.mjs`: **24 checks passed** at root and `/labadda-staging`:
bounded pages, no duplicate IDs across pages, state filters, two-attempt history,
expired-lease warning, no mutation controls, delayed-detail suppression, delegated
reader access and denied-refresh clearing. Desktop (1400px) and mobile (390px)
axe/overflow checks passed. Captured screenshots are in
`/tmp/labadda-inventory-jobs/{root,prefix}-{1400,390}.png` for this session.
Existing governance18 and accessibility34 checks also passed. Automated axe checks
are partial accessibility evidence; manual screen-reader/site/device gates remain.

Final full verification: **403 backend tests** including real recovery, no skipped
recovery and no model/migration drift; **31 frontend tests**, typecheck and build.
Additional failure tests prove that a lost completion reply remains discoverable
without duplicate execution, and completion audit failure cannot accept a receipt.
Independent operational, authorization and UI reviews found no substantive issue.

Reproduce on disposable state only: start `scripts/proxy-stack.sh start`, invoke
the fixture with `LABADDA_ENV=test`, each proxy database URL and its matching
`var/proxy-stack/{root,staging}/assets` directory, then run the browser script.
The flow grants and revokes Ben's operational delegation; reset fixtures before
other tests requiring that grant. No policy activation, file deletion or automatic
retry is performed. Job retries restart the scan; they are not resumable inventory
generations.
