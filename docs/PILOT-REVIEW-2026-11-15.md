# Critical review for the office pilot

Reviewed the 13–15 November change series on `main`, from the previously reviewed `7b674c1` to
`519d335` (438 files, approximately 32,698 added / 9,330 removed lines), followed by the fixes in
this candidate. Review prioritized identity/grants, durable writes, whiteboard/calendar workflows,
mail, backup/restore, shared-server installation and offline packaging. It combines source review,
independent reviewers, synthetic PostgreSQL/API tests and actual nginx/browser flows; it is not
an exhaustive security certification or evidence from the live office machine.

## Release decision

**Conditional candidate for a supervised pilot; office activation gates remain mandatory.**
The executable procedure and editable settings are in [the office rollout guide](OFFICE-PILOT-2026-11-16.md).
A final candidate validation report accompanies the downloadable release; it records the actual
commit, completed checks, advisory results and artifact fingerprints. Any failed mandatory check
blocks activation regardless of a readiness estimate.

## Material corrections

| Area | Finding and correction |
| --- | --- |
| Private boards | New client IDs did not meet the UUID API contract, preventing saves. Fixed IDs, separate per-board in-memory drafts, retained SPA drafts, guarded save responses and non-destructive late-session cleanup. Unsupported private image upload removed. |
| Shared boards | Secondary restore/snapshot actions could target board 0; previews/epochs crossed board views. Propagated indices, guarded late responses and blocked switching with pending writes. First-board-only panel/task actions are explicit. |
| Durable editing | Sticky/text edits erased the original before validating the replacement. Added atomic revisioned update, retained author/position, replay and undo support. Snapshot retries now bind full publication intent. |
| Accounting | Recharging one board removed other boards' logical charges. Added explicit scope, unambiguous object keys and multi-board reconciliation; incomplete totals remain labelled incomplete. Only derived ledger rows are rebuilt. |
| Calendar | Blind overwrites and physical deletion. Added expected revisions, identity/grant locks, retained cancellation, current posting policy, bounded aware dates/search/results and visible failure/conflict feedback. |
| Installer | Deleted the existing nginx default site; could remove retained assets before a failed restore. Preserve other sites; refuse nonempty/symlink restore targets and occupied ports. |
| Recovery | Cleanup could drop a non-test site. Require matching disposable provenance and refuse existing target names. Restore copies use their own Unix identity with mail/scheduler disabled. Copied backups now verify all bytes. |
| Operations | First-backup/doctor failures could still end in apparent success. They now fail commissioning. Explicit private-CA trust is respected by doctor probes. Unique release ID and same-ID/commit checks prevent skipped upgrades. |
| Interface | A floating board-item list covered toolbar controls; nested rename actions broke tab accessibility. Put the list in document flow and provide independent tab/rename/add controls and keyboard note alternatives. |
| Maintenance | Operator allowlist omitted the whiteboard limit. Older downgrade tests hit unrelated chosen-code fixtures; they now isolate the intended guard without weakening assertions. Demo reset is restricted to named local synthetic databases and no longer prints DB credentials. |

Migrations 0043–0046 are additive for user content and guard destructive downgrade. Migration 0044
rebuilds derived board charges, with incomplete coverage explicitly reported until reconciliation.
The owner approved **whitespace-only** formatting of already-pushed 0041/0042 on 15 November;
their parsed Python ASTs were checked unchanged. No historical migration behavior was changed.

## Quality and operational limits

Core access/transaction/recovery design is strong and has extensive denied-case tests. The recent
feature series introduced real data-safety and co-hosting defects that the ordinary happy-path checks
missed. Large UI/fixture/presentation modules and inconsistent styling still require maintenance;
passing tests do not remove that debt. Dependency age is separate from vulnerability status; the
candidate validation report records both and any exact owner-approved security exceptions.

Remaining site inputs are the actual hostname/IP, relay address and policy, certificate/browser trust,
resource headroom alongside PM, non-overlapping backup schedules, off-host recovery duration and
real-user accessibility/device acceptance. Ubuntu 24.04 was confirmed by the owner; the other
settings are conspicuous examples rather than guessed live values.

Start with 5–10 volunteers, one or two teams, approved non-sensitive data, a named operator/deputy,
and a first-day review. Health mail is not implemented: SMTP delivers submitted feedback only.
Physical panels are optional until tested on the real device. Full v1.0 completion, production-wide
rollout, retention/purge, portable archives and official-record workflows are outside this pilot.


## Executive assessment

**Code quality: 8/10. Engineering readiness for a supervised small pilot: 84/100.**
This is a weighted review judgement, not a measured probability of safe deployment or a v1.0
completion percentage. Final validation must be green; office acceptance is still pending.

| Aspect | Weight | Score /100 | Basis and remaining gate |
| --- | --- | --- | --- |
| Core workflows | 20% | 90 | Broad API and root/prefix browser coverage; physical devices still need acceptance. |
| Access and privacy | 20% | 90 | Owner/grant enforcement, denied-case tests and scoped independent review; no penetration-test claim. |
| Data integrity | 15% | 90 | Revision conflicts, atomic edits, retained cancellations and guarded migrations. |
| Deployment/co-hosting | 15% | 80 | Isolated paths/ports/services and safer installer; PM coexistence must be checked on the actual host. |
| Backup and recovery | 15% | 80 | Real PostgreSQL recovery and byte-verified copies; off-host restore time/RPO acceptance outstanding. |
| Operations | 10% | 60 | Status/doctor/timers documented; live monitoring, relay delivery and reboot acceptance remain. |
| Documentation | 5% | 90 | Office-specific commands and editable examples; actual values must be entered locally. |

Dependency remediation updates FastAPI/Starlette, multipart parsing, Pillow, certifi, pytest tooling
and the browser router. The owner explicitly approved the two requested exact age exceptions on
16 November: Pillow 13.0.0 and certifi 2026.10.23. Pillow has now reached 30 days; certifi's temporary
exception expires on 23 November. Other pins must satisfy the normal age gate. No telemetry exporter
or runtime external service was added. The security report is a dated published-advisory snapshot.

Proceed with office commissioning today; invite volunteers only after the office checklist passes.
Do not treat this score as approval to bypass a failed backup, trust, privacy or coexistence check.
