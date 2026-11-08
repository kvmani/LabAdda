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

## Full S4 workload over TLS (local rehearsal, 2026-11-08)

`scripts/rehearsal.py` adds the workload the eight-drawer soak did not cover. Thirty signed-in clients are split across two sibling workspaces (Thin Films and Catalysis). Eight draw; the other 22 read feeds and chat history and post chat messages. Every client holds a live socket. The run fails on any lost, duplicated or out-of-order board operation, any committed event a subscribed client did not receive, any event delivered to a client of the other workspace, or any request error, and on missed p95 targets when enforced. `LABADDA_PROXY_TLS=1 scripts/proxy-stack.sh start` now terminates TLS in nginx with a throwaway local CA and Secure cookies, so the rehearsal exercises https, wss and the proxy path.

**Finding and fix.** The first 30-client run showed p50 5.5 s and p95 18.9 s live-update latency, with 1,695 of 12,630 deliveries still outstanding at the end. Isolation and integrity held. The hub ran a separate database access check per receiving connection, one after another, in a task per event. It now keeps one ordered queue and worker per workspace, rechecks access once per batch for all receivers with the shared policy's eligible-reader rule, sends to receivers concurrently, and closes a client whose sends do not complete within 10 s instead of stalling the workspace. Fanout is now in commit order per workspace. The per-delivery recheck is unchanged in substance: it still runs after commit and before every send, including for direct database access changes that bypass the revalidation signal (`test_batched_recheck_drops_only_the_revoked_subscriber`).

[15-minute report](evidence/p4-tls-rehearsal.json), `--enforce-targets`, local TLS through nginx:

| Measurement | Result |
| --- | --- |
| Workload | 30 clients (8 drawers, 22 readers), 2 sibling workspaces, 900 s window (928 s with drain) |
| Host/path | Linux x86-64, 4 logical CPUs, loopback https/wss through nginx with a local CA |
| Board operations / chat messages acknowledged | 13,860 / 1,246 |
| Live deliveries expected / missing | 226,590 / 0 |
| Cross-workspace deliveries | 0 |
| Lost / duplicated / revision gaps / request errors | 0 / 0 / none / 0 |
| Compaction during run | both boards (through revisions 6,050 and 6,066) |
| Live update latency (every event × receiving client) | p50 26.2 ms, p95 48.9 ms, max 3,977.9 ms |
| List latency (feed, chat history, workspace list) | p50 19.4 ms, p95 48.7 ms (3,769 samples) |

The 15-minute run used the batched hub before two small follow-ups: the slow-client timeout and normalizing string workspace IDs in `publish`. A 120 s rerun on the final code also passed with targets enforced: 34,260 deliveries, none missing, p95 55.2 ms, max 439.5 ms. The single ~4 s maximum in the long run is unexplained; the likely suspect is board compaction holding the board lock, but this was not verified. It is recorded rather than averaged away and should be watched on the VM. Activation is rate limited per client address. The local stack raised `LABADDA_LOGIN_ATTEMPTS_PER_WINDOW` for the disposable run; against an unmodified server the harness waits the limit out.

### Compaction lock follow-up

The ~4 s maximum suggested compaction stalls. Scheduled compaction folded the whole history prefix while holding the board row lock, and then invalidated the board state cache, so the next stroke refolded under the lock. Compaction is now two-phase. The fold runs without any lock, since committed operations at or below the new base never change within an epoch. The lock is then taken only to recheck epoch and base and to write the snapshot. The state cache is keyed by epoch and revision, so it survives compaction. New tests show that a stroke commits while a compaction fold is paused, a restore during the fold makes compaction skip instead of writing a stale snapshot, and no refold happens after compaction. Each compaction now logs `fold_ms` and `locked_ms`.

[Second 15-minute report](evidence/p4-tls-rehearsal-2.json), same command and host: 13,875 board operations, 1,242 chat messages, 226,755 deliveries, 0 missing, 0 cross-workspace, 0 lost/duplicated, p50 28.7 ms, p95 55.6 ms, **max 1,877 ms** (down from 3,978 ms), list p95 54.3 ms. The remaining maximum is not root-caused. Candidates are the locked delete/snapshot write, garbage collection, or CPU contention with the 30-client harness on the same 4-CPU host. The new compaction timing logs let the staging VM run separate these.

## Automated accessibility audit

`e2e/accessibility.mjs` runs axe-core (WCAG 2.1 A/AA rule tags) on 12 views at both root and prefix, including mobile and the touch panel. It also checks the skip link, visible keyboard focus and phone-width overflow. The first run found one serious contrast failure (muted text on the active rail highlight); the shared muted colour was darkened. The final run passed 34 checks with no findings at any severity. [Evidence](evidence/accessibility/README.md). A shell skip link was added for keyboard users.

## Still open for P4 step 4

This is a local rehearsal on a shared development host, not the representative staging VM, the site's TLS certificates or its network path. Run the same command on the staging VM over the site proxy and record VM resources, path and browser versions. A manual screen-reader, zoom and visual review, the physical pen/finger panel test, off-host recovery and site-owner acceptance also remain. REVIEW.md asks for an independent reviewer for realtime changes; the hub restructuring above has been self-reviewed and regression-tested, but not independently reviewed.
