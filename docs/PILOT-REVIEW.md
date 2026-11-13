# Small-pilot readiness review — 13 November 2026

Scope: latest `main` at review start (`3d9adeb`), focused on current-access realtime delivery,
session revocation, the operational environment parser and the documented pilot gates.
Independent review: `pilot_review`; inspected the corrections and exercised isolated preview
and presence regressions. This is a focused engineering review, not an exhaustive security audit.

## Findings corrected

| Severity | Finding | Correction and evidence |
| --- | --- | --- |
| High | Live board previews trusted cached sender/recipient permissions; presence also used stale subscriptions. Expired or revoked sessions could retain transient content access. | Current sender authorization, checked recipient delivery and presence filtering with subscription generations. Logout, activation/reset and password changes notify the hub after commit. `test_preview_access.py` covers actual DB expiry, idle timeout, revocation, membership loss, archived spaces and concurrency; `test_realtime.py` covers auth-driven socket closure. |
| High | The shipped environment template included 27 settings rejected by the operational parser, blocking commissioning, upgrades and scheduled backups. | Explicitly allow the documented bulk-change, metrics/activity and health settings. `test_lifecycle.py` validates the complete template; unknown settings remain rejected. |

The independent re-review also identified sequential stale-socket cleanup delaying healthy
presence. Cleanup and healthy delivery now run concurrently; an event-controlled regression
verifies healthy delivery before the stalled cleanup finishes.

## Validation evidence

The final main verification passed: **1,528 backend tests, zero failures/errors/skips**, with
real recovery enabled; **218 frontend unit tests**; clean docs/help, Ruff, ESLint/Prettier,
types, migration drift and production build. Browser checks passed:
main flows 69, component gallery 18, profile 32, governance 18 and console backups 56 (193 total).
These suites cover root and prefixed deployment behaviour; this review did not rerun every
browser suite or the 15-minute soak.

Two short TLS rehearsals used 30 clients, 8 drawers and two sibling workspaces, with a configured
30-second workload per root/prefix instance. Both met the enforced latency targets. Root:
11,835 expected deliveries, update p95 63.7 ms and list p95 167.7 ms. Prefix: 11,685 expected
deliveries, update p95 97.5 ms and list p95 199.0 ms. Neither run reported missing deliveries,
isolation violations, lost edits, duplicates or revision gaps. These are local cloud smoke
results under synthetic load, not site capacity measurements or long-duration stability proof.

## Readiness judgement

**76/100 — conditional readiness for a small supervised pilot; changes to the real site are
not authorised by this score.** The score is reviewer judgement, not a certification or the
percentage of v1.0 finished. Weighted dimensions: core workflow 90 (20%), privacy/access 85
(25%), reliability/recovery 80 (20%), site operations 55 (25%), adoption/ownership 70 (10%).
No real participant or organisational data was used for this review.

Before introducing real users and data, complete the owner gates in
[track D](plan/deployment.md) and the [pilot runbook](PILOT-RUNBOOK.md):

1. Rehearse installation and lifecycle on Ubuntu 24.04 with the approved PostgreSQL 16 patch,
   actual systemd units/timers, reboot persistence and trusted nginx TLS.
2. Copy a verified backup off the application VM; restore into an isolated target and record
   measured recovery time, recovery point and access/content checks.
3. Agree identity, accounts, data scope and incidents; name the operator and at least two
   administrators. Review sibling-section and parent access with representative participants.
4. Perform real-browser/screen-reader and physical touch-panel checks where the panel is in
   scope. Resolve or explicitly record site acceptance of unknown checklist items, including
   the restore item whose evidence is maintained outside the application.
5. Obtain the site owner's acceptance. Do not appoint unit administrators until the documented
   owner decisions are settled. Full quotas, retention/purge and portable archives remain outside
   this pilot's delivered scope.

Suggested pilot: 10–20 volunteers across 2–3 teams for four weeks, with approved limited data,
a week-one review and existing source records retained. Measure repeat use, time to find an
update/follow an action, task follow-through, access incidents, backup success and restore time.
Pause for an unresolved high-priority privacy or durable-data issue. These are proposed pilot
parameters, not an already approved site configuration or measured benefit.

The cloud machine is a Debian development environment with user-owned PostgreSQL and nginx;
it does not establish the Ubuntu deployment gates. Presentation files and fictional screenshots
are downloadable artifacts outside Git, not release assets.
