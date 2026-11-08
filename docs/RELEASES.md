# Offline releases

The release tooling implements P4 step 2. Backups/restores, TLS and physical-panel acceptance, dependency scanning and independent pilot approval remain separate gates. Never activate a pilot merely because an archive installs.

## Connected build and transfer

Use a clean committed checkout on **Ubuntu 24.04 x86-64, Python 3.12 and Node 22**, with the locked dependencies installed as in README. Run `scripts/verify.sh` first. Build with:

```bash
.venv/bin/python scripts/release.py build --release 0.1.0-COMMIT --output /path/outside/checkout
```

The archive includes committed application source, migrations, built frontend, a binary-only wheelhouse from `backend/requirements.lock`, deployment templates, operator documentation, and the release tool. No Node runtime is needed after installation. The complete lock currently includes test dependencies as well as runtime dependencies. Python wheel and bundled frontend dependency metadata and license/notice texts are inventoried under `licenses/` and in `manifest.json`; review missing or ambiguous license declarations before distribution. This inventory is not a legal clearance or vulnerability scan. Scan the candidate on the connected builder and retain approved provenance and scan evidence independently.

The manifest records the full build commit, actual OS/version, architecture, Python minor version, schema head, dependency inventory, sizes and SHA-256 hashes. The installer requires an exact platform match; a Debian development build is not an Ubuntu release. OS packages are not bundled: provision Python 3.12 with venv/ensurepip, PostgreSQL 16, nginx and site CA trust through an approved internal Ubuntu mirror before disconnecting. Keep PostgreSQL, writable assets and operator config outside releases.

Transfer the archive through the approved process. Deliver its `.sha256` digest through a separately authenticated channel. A digest beside an untrusted archive proves no publisher identity. Use a trusted local copy of `scripts/release.py` to inspect/install; do not execute tools extracted from an unverified archive.

## Verify and install without network

```bash
python3.12 /trusted/release.py verify /transfer/labadda-VERSION.tar.gz --sha256 TRUSTED_DIGEST
python3.12 /trusted/release.py install /transfer/labadda-VERSION.tar.gz \
  --sha256 TRUSTED_DIGEST --instance /srv/labadda/staging
```

Installation checks archive digest, member types/paths, duplicates, resource limits, complete manifest coverage, payload hashes, platform, required files and disk capacity before extraction. Only regular files are accepted. Each release gets its own venv at its final path; pip uses `--no-index` and the bundled wheelhouse exclusively. An installation failure removes only the candidate it created. Existing releases and state are retained. Repeating the same release ID is refused instead of overwriting it. The installation root must be operator-owned and inaccessible to untrusted writers; do not run as root. Release files and venvs must remain immutable to the running application in production (separate deployment and runtime identities where site policy permits).

Set operator-owned configuration from `deploy/labadda.env.example` using secure file permissions. Do not source arbitrary environment files as shell scripts. Required preflight before activation:

- Confirm the staging/pilot instance name, database role and database, distinct cookie name, base path and proxy route; use `LABADDA_ENV=staging` or `pilot` so fixture commands are refused.
- Confirm asset, log and backup paths are outside the release tree and writable by the intended identities. Confirm sufficient space for both the candidate and retained recovery point.
- Validate the site TLS certificate, trusted origin, nginx configuration and user-service persistence. Ensure only the proxy can reach the app listener.
- Verify a consistent recovery point and quiesce **all** writers: app, reminder runners, CLI jobs and sockets. Keep the proxy in maintenance during migration and activation. The flags below attest operator checks; the tool does not create backups or stop traffic.

With the operator environment loaded securely, apply migrations once from the candidate:

```bash
/srv/labadda/staging/releases/VERSION/venv/bin/python -m labadda.cli migrate
```

Run runtime preflight with the same securely loaded service environment:

```bash
python3.12 /trusted/release.py preflight --instance /srv/labadda/staging --release VERSION
```

It checks retained payload hashes before executing the candidate, validates staging/pilot identity, cookie/TLS settings and asset isolation, and reads the live database schema. Activation repeats these checks and compares the live schema with the supplied expectation. Activate only after migration succeeds and the observed schema is `0005`:

```bash
python3.12 /trusted/release.py activate --instance /srv/labadda/staging \
  --release VERSION --database-schema 0005 --writers-quiesced --backup-verified
```

`current` changes with a single atomic symlink replacement. Runtime environment and assets stay outside it. Configure the service to use `current/venv/bin/python -m labadda.cli` and `current/backend` as its working directory. Restart the service, then probe `/healthz`, `/readyz`, the app shell and a hashed asset through the real proxy. Sign in with a designated synthetic account, verify a permitted workspace, a denied sibling workspace, and WebSocket upgrade at root and the configured prefix. Check logs without recording credentials or content. Reopen traffic only after these checks pass.

## Failed activation and rollback rule

Keep traffic in maintenance after any failed migration, restart or health/functional probe. Retain the candidate and sanitized failure evidence. Read the current database schema again. A code rollback is allowed only when the retained release declares **the exact same schema** as the database:

```bash
python3.12 /trusted/release.py rollback --instance /srv/labadda/staging \
  --release PREVIOUS_VERSION --database-schema 0005 --writers-quiesced --backup-verified
```

Restart and repeat the same probes. If schemas differ, the tool refuses the pointer change. Do not automatically downgrade migrations or rewind user data. Use the operator-approved database-and-assets restore procedure (P4 step 3), or repair forward, while remaining in maintenance. The tool switches code only and makes no automatic recovery claim.
