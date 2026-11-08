# P4 step 2 evidence — 2026-11-08

Source candidate: `f20e1d383f34e27f426eb6b3c2f72504eddda1cc`. This is engineering evidence on synthetic data, not pilot approval. Read [RELEASES.md](RELEASES.md) for the operator procedure and remaining gates.

## Verified results

- `PATH=/workspace/tools/node22/node_modules/node/bin:/workspace/tools/node22/node_modules/.bin:/workspace/tools/bin:$PATH scripts/verify.sh`: **151 backend tests passed**, including **29 release tests**; Alembic reported no new upgrade operations; TypeScript passed, **3 Vitest tests passed**, production build passed. Python 3.12.14, PostgreSQL 16, Node 22.22.0 on the Debian development host. A dependency deprecation warning remains in Starlette's test-client integration with AnyIO; no failed or skipped tests.
- The existing `scripts/proxy-stack.sh start` and `node e2e/flows.mjs http://127.0.0.1:8080 '' /labadda-staging` completed **64/64 browser checks** through real nginx with shared Chromium, then the test stack stopped. Root/prefix isolation, authorization, collaboration and touch-session behavior were exercised. The initial browser attempt ran zero checks because its executable path was absent; a local mapping to the provided Chromium fixed the setup and the full rerun passed.
- Independent deployment review found and verified corrections for transfer-path replacement during extraction, optimized-away preflight assertions, execution before payload validation, asset isolation across releases, competing temporary activation links, missing frontend license inventory, and inherited pip source configuration. Regression tests cover these paths. Wheel license directories exposed a further build failure; directory entries are now skipped and covered by a regression test.

## Target-platform build and offline install

A connected Ubuntu 24.04 x86-64 container with Python 3.12.3 and Node 22.22.0 built the archive using:

```bash
python3.12 scripts/release.py build --release 0.1.0-f20e1d3 --output /workspace/releases
```

The builder installed Python/venv, CA certificates, git and libstdc++ from signature-verified Ubuntu repositories. Managed proxy CA trust remained enabled. Rehearsal image ID: `sha256:0d92da4744c60061adab8ffe5cea8089dbeb6d6e83d0e365367a1709bfd9dbb2`.

Archive: `/workspace/releases/labadda-0.1.0-f20e1d3.tar.gz` (approximately 23 MB).

SHA-256: `8e7098927317a3ea71d67f4b08904945212191f6ad82deacc937df2901e4c30a`.

A fresh Ubuntu container, non-root UID 1000, **`--network none`**, no Node runtime, and empty installation directory ran:

```bash
python3.12 /trusted/release.py install /transfer/labadda-0.1.0-f20e1d3.tar.gz \
  --sha256 8e7098927317a3ea71d67f4b08904945212191f6ad82deacc937df2901e4c30a \
  --instance /rehearsal/instance
```

The test deliberately injected an external `PIP_FIND_LINKS`; installation still used only the bundled wheelhouse and passed the installed dependency/schema import checks. Network isolation was enforced by Docker, rather than inferred from pip output.

A separate container attached only to an internal Docker network used that installed release and a disposable PostgreSQL database. Proxy variables were cleared for this deliberately disconnected rehearsal. Migrations and synthetic seeding succeeded. At `/` and `/labadda-staging`, the installed app passed readiness, app-shell and hashed-JavaScript loading, fixture sign-in, workspace listing, and an explicit **403** for non-admin access to the admin directory. Both server processes terminated cleanly.

With staging identity, TLS-cookie/origin and external asset settings, live preflight observed schema `0005`. Activation expecting `0004` failed and left `current` absent. Activation expecting `0005` atomically created the correct release pointer. Unit tests additionally switch between distinct candidate/previous releases, preserve external state, and refuse schema mismatch or tampering without altering `current`. No automatic database downgrade or data rollback was performed.

Sanitized current-instance logs and the smoke harness are retained under `/workspace/setup/`: `final-verify.log`, `browser.log`, `release-build.log`, `offline-install.log`, `offline-smoke.log`, `activation.log`, and `offline-smoke.py`. The archive and digest are retained outside the checkout. Future-task snapshot restoration has not been independently tested.

## Remaining gates

The offline release implementation and clean target-platform installation are verified. Site deployment still requires the separately authenticated transfer/provenance process, dependency/artifact scanning and license approval, actual internal OS provisioning, real TLS/proxy/service-persistence rehearsal, and site-owner acceptance. A wheel/frontend license inventory does not establish distribution clearance; the repository currently has no application LICENSE file. The next implementation slice is writer-quiesced database-and-assets backup/restore, including restored-session revocation. Physical pen/finger acceptance and the representative TLS load/accessibility rehearsal remain open.
