# Operational automation qualification · 2026-11-11

Code candidate: `b82f23acaaf7c47f477172868dd3dea387dc60d5` (schema0025).
The owner requested deployment, upgrade, maintenance, backup/DR automation and a
dedicated realistic multi-user regression system. Implementation starts at the
[operations guide](../../development/operations.md),
[commissioning runbook](../../COMMISSIONING.md) and
[simulation guide](../../development/simulation.md).

| Delivered slice | Verification |
| --- | --- |
| Exact site config, hardened system service, proxy maintenance, readiness |27 site tests; actual generated nginx configuration checks passed at root/prefix using local CA |
| Serialized fail-closed backup/upgrade |18 lifecycle tests; service stop/active-state, backup/migration/probe failures, contention, delayed startup, TLS allowlist and redacted deadlines;30 existing release tests |
| Dedicated simulation and CI |8 runner tests;12 workload report gates; locked Playwright; full profile passed465 browser checks across11 suites; explicit listener/PID shutdown confirmed |
| Isolated initialization/restore |10 commissioning tests including real PostgreSQL empty/nonpublic occupied target; enhanced full PostgreSQL backup/restore passed with namespace bypass regression, content/asset/reply/task/preference preservation and credential revocation |
| Full application qualification |573 backend checks before commissioning; ten new commissioning checks and enhanced real recovery rerun afterward; model/migration drift clean;31 frontend tests, typecheck and production build passed |
| Offline release |Built and independently rehashed archive; verified192 payload files include all three operational scripts/runbooks; installed from bundled wheels with no index/network and revalidated installed payload |

Independent deployment review found and verified corrections for probe deadlines,
service startup readiness, PostgreSQL TLS configuration, fresh CI databases,
cleanup proof, SIGTERM handling, omitted task suites, missing service units and
nonpublic namespace checks. No code-review blocker remains for the next milestone.
This is local engineering evidence, not permission to activate a real site.

## Multi-user results

Each workload used30 signed-in synthetic clients/eight drawers/22 readers across
two sibling sections, for90 seconds over TLS, with latency gates enforced.

| Route | Board ops | Chats | Expected deliveries | Missing/lost/duplicates/isolation | Update p95 | List p95 |
| --- | ---: | ---: | ---: | --- | ---: | ---: |
| Root |1655|143|26970|0 / 0 / 0 / 0|56.5ms|see JSON|
| Prefix |1654|142|26940|0 / 0 / 0 / 0|54.4ms|see JSON|

All clients subscribed, no revision gaps, no request errors. The full browser
profile includes five-person attachment/private-group flows, owner/shared tasks,
assignment/discussion, board references, conversation conversion, live reconnect,
threads, dashboard and preferences, with each suite freshly seeded at both routes.
Machine-readable details and actual list latencies: [qualification.json](qualification.json).

Local evidence directory: `/workspace/artifacts/simulation-2026-11-11-full` contains
stage logs, screenshots, both workload reports and the full backend/frontend log.
The quick run remains separately in `simulation-2026-11-11-quick`.

## Deployment limits and next action

The23MiB offline archive at
`/workspace/artifacts/labadda-operations-release-2026-11-11/labadda-ops-20261111.tar.gz`
is a **local Debian13/x86_64/Python3.12 validation artifact**. Its trusted digest and
platform are recorded in JSON. The deployment contract targets Ubuntu24.04: build
and validate a new archive on that target platform before site installation;
the release tool deliberately rejects platform mismatches. Never bypass that gate.

This environment cannot prove actual systemd boot/restart/persistence or host
permissions. Hosted CI has not been observed. Real site certificates/DNS/CA,
least-privilege roles, disk encryption/capacity, off-host encrypted transfer and
separately retained digests, representative endurance, manual accessibility,
physical panel and a timed isolated restore proving site RPO/RTO remain open.
Commissioning stops with traffic closed; external writer isolation and restored
runtime ownership require operator verification. No site host was provisioned,
no real content restored, no demo data reset and no user traffic switched.

Next: use a disposable Ubuntu24.04 systemd host with owner-provided site settings;
render/review, build/install the target release, initialize while isolated, create
a verified baseline backup, activate and qualify, rehearse upgrade/fail-closed
failure and restore from the off-host copy into another isolated target. Record
actual timings and owner acceptance before first rollout.
