# P4 engineering qualification — 2026-11-08

Five successive runnable slices were committed to main: verified recovery bundle primitives, quiesced PostgreSQL-plus-assets backup, isolated restore and credential revocation, a full recovery/authorization rehearsal, and measurable performance qualification. Physical and site-owned gates remain open.

## Recovery and regression evidence

`LABADDA_RECOVERY_TESTS=1 scripts/verify.sh` passed **179 backend tests**, including 17 focused recovery checks, one real PostgreSQL recovery round trip, nine soak-report checks and the existing release/application suites. No tests were skipped in this run. Alembic detected no model/migration drift. TypeScript, all **3 frontend unit tests** and the production build passed. PostgreSQL server and clients were 16.15; Python 3.12.14 and Node 22.22.0 ran on the cloud development host. A Starlette/AnyIO test-client deprecation warning remains.

The recovery test creates synthetic posts, chat, board operations, a PDF and a personal note, performs a real custom-format dump and isolated restore, then verifies content through the application. Copied normal/panel cookies and pending pairing/activation codes are refused; fresh sign-in works; sibling content and another user's private notes remain inaccessible. Reusing a populated target is refused. The test cleans up only the uniquely named target database it created. Focused tests exercise corruption, missing/extra files, links, permissions, failed dump cleanup, overlapping paths and ambiguous connection selectors. Independent deployment review identified and verified fixes for path overlap, durable asset publication and consistent database endpoint selection. [Recovery procedure](RECOVERY.md).

The first standalone restore rehearsal exposed a missing explicit pg_restore database selector; corrected before the successful real restore and integration test. Initial integration harness attempts used nonexistent upload/single-post endpoints; corrected to the existing upload and workspace-feed contracts. No application behavior was weakened to make the tests pass.

## Eight-drawer local rehearsal

Command, against a fresh disposable nginx test stack:

```bash
scripts/proxy-stack.sh start
.venv/bin/python scripts/soak.py --drawers 8 --seconds 120 --enforce-targets --out /tmp/p4-soak.json
scripts/proxy-stack.sh stop
```

The command exited successfully. [Machine-readable measured report](evidence/p4-local-soak.json):

| Measurement | Result |
| --- | --- |
| Workload | 8 synthetic drawers, 120 s drawing window, 123.54 s including observer drain/final check |
| Host/path | Linux x86-64, 5 logical CPUs, loopback HTTP through nginx |
| Acknowledged / observed operations | 3371 / 3371 |
| Lost / duplicated operations | 0 / 0 |
| Revision gaps / request errors | none / 0 |
| Compaction | through revision 1614 during the run |
| Committed update latency | p50 27.2 ms, p95 66.0 ms, max 529.1 ms |
| Ordinary list latency | p50 14.5 ms, p95 37.5 ms (678 samples) |

The full verification suite ran concurrently for part of this rehearsal. This is a shared development environment measurement, not a representative site capacity claim. `--enforce-targets` makes p95 >=500 ms for updates or >=1000 ms for lists fail the process, in addition to data/delivery failures. Zero-operation runs cannot pass. Reports include sample counts, platform, TLS status and actual elapsed time, and use JSON null rather than NaN for missing metrics.

## Remaining site gates and immediate next action

Run the **15-minute** S4 rehearsal on the representative staging VM over the site's real TLS/proxy path, with 30 signed-in clients, eight drawers and two active sibling workspaces. Record VM resources, browser versions, path and evidence; the current harness supplies eight-drawer coverage but does not simulate the full 30-client/two-workspace workload. Add that workload before claiming the full S4 gate. Complete keyboard/accessibility and visual review, physical pen/finger and kiosk acceptance, verified off-host recovery transport and retention, and real service-persistence/restart checks. Then perform the final independent candidate review and site-owner acceptance in REVIEW.md and DEPLOYMENT.md. Do not activate real pilot data based on these synthetic results.

The local logs are retained under `/workspace/setup/`: `five-step-verify.log`, `step5-soak.log`, `step5-soak.json`, and `step5-stack.log`. Hosted CI is configured for recovery testing but has not been observed completing in this session. No new release archive was built in these five steps; the previous archive remains historical evidence for its recorded source commit. Build a fresh target-platform release after the remaining candidate changes and checks.
