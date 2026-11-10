# Assignment and My Tasks evidence

Synthetic validation on 2026-11-10. Backend full verification passed446 tests with
real recovery and no migration drift; frontend typecheck,31 tests and production
build passed. Final targeted assignment/workflow/recovery validation passed23 cases.
Independent authorization/concurrency and UI reviews found no substantive issue
after final-grant cursor suppression was added.

`e2e/task-assignment.mjs` passed46 root/prefix checks using five synthetic colleagues:
section picker excludes siblings/parent-only/admin/inactive users; personal picker
contains only owner/unassigned; real assignment, completion and My Tasks filters;
ancestor/group assignments; unknown PUT reply resolved by reload without blind
retry; concurrent edit conflict retains chosen colleague; membership revocation
removes shared tasks while personal ones remain; delayed dashboard response cannot
override a changed filter. Desktop/390px mobile axe/overflow passed for My Tasks,
and the mobile assignment picker. Screenshots are generated in the supplied output
directory (default `/tmp/labadda-assignment`).

Existing `e2e/todos.mjs`66 task checks also passed on the final assignment source.
Run on fresh disposable proxy fixtures: the assignment and task scripts revoke
Ben's Section A grant, so reset between membership-dependent flows. These tests
are engineering evidence, not real-site/manual accessibility/device acceptance.

The backend blocked-target regression waits for actual PostgreSQL identity locking,
then deactivates the target and proves final eligibility rejects the assignment.
Reciprocal writers both finish without losing revision/history. Recovery preserves
assignment/history while revoking copied sessions; downgrade also protects past
responsibilities after unassignment. Source/contract: [assignment guide](../../development/task-assignment.md).
