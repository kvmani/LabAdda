# Multi-user regression system

`scripts/simulate.py` owns a **disposable local** root/prefix stack. Start here for
collaboration qualification; source contracts remain in the feature guides.
It is not a production load generator and accepts no remote origin/database.
Only `labadda_e2e_root` and `labadda_e2e_prefix` on the fixed fictional localhost
PostgreSQL connection are reset. Development/research demos are preserved.
Do not concurrently run `proxy-stack.sh`, individual browser tests or another
runner against ports8001/8002/8080. The runner lock covers other runner invocations.

Install locked backend/frontend dependencies, build the frontend, install nginx,
PostgreSQL16 clients, Node22 and Chromium. Provision the fictional local role
`labadda`/`labadda-dev` and its two **disposable** databases `labadda_e2e_root`
and `labadda_e2e_prefix` before the first run (CI does this explicitly). Then install the locked browser driver:

```sh
npm --prefix e2e ci
# Plan only; no stack or output directory is created:
.venv/bin/python scripts/simulate.py --profile quick --out /tmp/labadda-simulation
# Explicit destructive opt-in, new exclusive private output directory each run:
.venv/bin/python scripts/simulate.py --profile full --out /tmp/labadda-simulation --apply-disposable
```

`LABADDA_CHROMIUM` selects an installed Chromium executable (default
`/usr/bin/chromium`); other LabAdda/PostgreSQL selectors are replaced with the
runner's fixed synthetic configuration. Run as the development operator, never
root or a production service account. Staging/pilot service environments are
refused. Inspect `--profile quick` first on a new development host.

The **quick** profile runs five-person chat/file/private-group and alert/browser
flows at root and prefix, then two TLS workloads of five clients/two drawers for
20 seconds each. The **full** profile resets fixtures before each of eleven suites:
legacy collaboration/touch, personal/shared todos, assignments, task discussions,
live task catch-up, conversation conversion, board references, chat threads,
five-person chat attachments/private groups, dashboard and alert preferences.
Each suite tests root and prefix. Negative cases include sibling isolation,
revocation during held responses, private content, uncertain retries, retained
drafts, reconnect and mobile/accessibility checks where implemented in the suite.
Full load uses30 clients/eight drawers/22 readers/two sibling workspaces for90s
at **each** TLS route. A representative-site long rehearsal remains separate.

Workloads fail on missing subscriptions, missing/duplicate/lost updates, revision
gaps, foreign deliveries, request errors or enforced latency failures. Direct
`scripts/rehearsal.py` usage now requires `--synthetic-target`: an explicit operator
attestation that its target is disposable development/test, never production.
Do not aim it at real user content. The managed runner supplies this flag itself.

Each stage has a timeout and private synthetic log. Failures stop later stages.
An atomically replaced/fsynced `report.json` records each started/completed stage,
including interrupted attempts, and reports failure until all stages and cleanup
pass. Browser screenshots remain under that output directory. The final cleanup
checks listeners and recorded app PIDs, rather than trusting the legacy stop
script's exit code. SIGTERM/keyboard cancellation reaches cleanup and foreground
process groups are terminated on timeout. SIGKILL/host failure cannot run cleanup;
inspect the report, then explicitly stop only the disposable stack:

```sh
LABADDA_RUN_DIR="$PWD/var/simulation-stack" scripts/proxy-stack.sh stop
```

No unsafe partial-stage resume: rerun into a new output directory from fresh
fixtures. Evidence contains synthetic content only; keep outputs private and do
not upload actual service environment files, dump/asset bundles or credentials.
GitHub CI has a separate full simulation job and seven-day synthetic evidence
artifact. Hosted CI execution is only verified after observing its run, not by
adding YAML. Unit gates: `test_simulation.py`, `test_rehearsal_report.py`.
