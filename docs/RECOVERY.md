# Backup and isolated recovery

Use PostgreSQL **16** client tools (`pg_dump`, `pg_restore`) alongside the normal Python dependencies. Recovery bundles contain content, password hashes and historical credentials: keep them in private operator-owned directories, encrypt transferred/off-host copies through the approved site process, and restrict retention and access. Hashes establish integrity, not publisher identity. Record the printed manifest digest through a separately authenticated channel. Do not accept an untrusted dump: PostgreSQL restores execute SQL.

## Create a recovery point

Put the proxy into maintenance. Stop the application process (including its socket hub and scheduler), standalone reminder jobs and all other CLI writers. Verify those processes stopped. Keep them stopped until the command finishes. The flag below attests that operator action; it does not stop services. The tool additionally takes SHARE locks on public tables, with a 10-second lock timeout, while creating the database dump and asset copy. Stable before/after asset hashes detect changes; these checks do not replace stopping writers or DDL.

Securely load the source's `LABADDA_DATABASE_URL` and `LABADDA_ASSET_DIR` without logging credentials. Database URLs must explicitly name host, port, username, password and database, with no query options. Remove ambient `PG*` connection selectors; only explicit `PGSSL*` trust settings are retained. This ensures Python guards and PostgreSQL tools reach the same database. URL-encode special characters in credentials. Production TLS verification remains required.

```bash
.venv/bin/labadda backup /private/backups/RECOVERY_ID \
  --release FULL_RELEASE_COMMIT --writers-quiesced
```

Choose a new destination outside release code and the asset tree. Publication happens only after dump, asset inventory, manifest validation and filesystem synchronization. The manifest records release, schema, source database name, recovery-point time, file sizes and SHA-256 hashes. The custom-format dump excludes role ownership and ACLs. Copy the completed bundle off the application VM using the approved process; authenticate and verify that copy before trusting the backup. Do not assume a snapshot of this development workspace is a production backup.

## Scheduled backups and the status file

`deploy/systemd/labadda-backup@.service` and `labadda-backup@.timer` run the lifecycle backup every night (default 02:30, with a random delay of up to ten minutes, and a missed run is made up when the host starts). Install both under `/etc/systemd/system/`, adjust the tool path and the site description file name in the service, then `systemctl enable --now labadda-backup@<instance>.timer`. The unit runs

```bash
python3 -I <tools>/scripts/lifecycle.py --site /etc/labadda/<instance>.site.json backup \
  --unattended --apply --external-writers-stopped --resume-after-backup --destination-alias local
```

`--unattended` takes the expected release and schema from the installed site instead of a reviewed plan (use the reviewed `--expected-current/--expected-schema` form for manual runs). `--external-writers-stopped` is your attestation that no other LabAdda command runs at that hour. `--resume-after-backup` restarts the service and lifts maintenance only after the backup was taken and its bundle was re-checked against its manifest; if anything fails, the site stays in maintenance exactly as for a manual backup. **The site is unavailable while the backup runs**; choose a quiet hour.

After every run, success or failure, the tool writes `backup-status.json` into the directory named by `LABADDA_STATUS_DIR` (an existing directory owned by the operator, not group- or world-writable, readable by the service account). The file is written to a temporary file, flushed, and renamed over the old one, so a crash leaves the previous file whole. It holds only these fields, defined once in `backend/labadda/backup_status.py` and used by both the tool and the application:

| Field | Meaning |
| --- | --- |
| `format` | Always `1` |
| `finished_at` | UTC time the run ended, `YYYY-MM-DDTHH:MM:SSZ` |
| `result` | `success` or `failure` |
| `size_bytes` | Size of the finished bundle; `null` on failure |
| `verification` | `passed`, `failed` (the bundle did not match its manifest) or `not_run` |
| `destination` | Short label for where backups are kept, e.g. `local` (`--destination-alias`) |
| `schema`, `release` | Database schema and release that were backed up; `null` on failure |

No paths, host names or secrets are ever written, and a reader rejects any file with other fields, odd values or more than 4 KiB. A missing file means backups are **unknown**, never healthy. A site without `LABADDA_STATUS_DIR` still backs up but records nothing. A success needs a passed verification; the bundle's manifest check is repeated by `labadda verify-backup <bundle> --manifest-sha256 <digest>`.

### Keeping the newest local backups

The timer's second step runs `lifecycle.py ... prune-backups --keep 7 --apply` only after a successful backup. Run it without `--apply` to see the plan: which finished backups would be kept and which removed, nothing deleted. Only directories created by the lifecycle tool that contain a manifest are counted or removed; unfinished bundles and other files are reported and left alone. It runs under the same lock as backups and upgrades and is journaled. Local retention is not off-host durability: copy bundles off the VM by the approved process before relying on them.

## Restore without exposing traffic

Provision a **new empty database with a different name**, a new asset path that does not exist, distinct cookies/instance identity and isolated proxy/service configuration. Do not restore over a running or existing database. Use an operator restore role with the required DDL rights; application runtime permissions should remain separate where supported. Keep the target off traffic and keep all writers stopped.

Set `LABADDA_RESTORE_DATABASE_URL` to this explicit target URL and `LABADDA_ASSET_DIR` to its new asset path; the source URL is not used by restore. With the trusted recorded manifest digest:

```bash
.venv/bin/labadda restore /private/backups/RECOVERY_ID \
  --manifest-sha256 TRUSTED_MANIFEST_DIGEST --isolated-target
```

The tool copies the bundle privately and validates that exact snapshot before touching the database. It refuses links, extra/missing/modified files, incompatible schema, source-name reuse, populated target databases and paths overlapping the preserved bundle. A target advisory lock prevents competing restores. `pg_restore` uses a single transaction. After import, the tool verifies schema and committed asset references/hashes, preview presence and recorded preview size/hash expectations, revokes **all** copied normal/board sessions, and deletes copied pairing and activation/reset tokens and operational-reader delegations plus copied pending upload reservations and request receipts. Recreate operational delegations explicitly after verified recovery; a backup may predate a revocation. Upload deduplication does not survive restore: inspect recovered content before starting new uploads, rather than blindly resending old request keys. Assets publish atomically only after those checks. It never automatically changes a current-release pointer or proxy route.

A failure after database import can leave a populated target database even when assets are unpublished. **Keep it isolated.** Retain sanitized evidence, investigate, and retry using another freshly provisioned empty database and absent asset path. The tool never drops databases, rewinds production data, or retries over partial state. Do not log SQL dump contents or credential-bearing exceptions.

After success, configure the isolated service to use the restored database/assets and the manifest's compatible release. Give its runtime identity the necessary private access to assets through site-approved ownership/ACLs; never make assets public to fix permissions. Restart with an empty in-memory socket hub. Check liveness/readiness and assets through the real proxy, then sign in afresh with designated synthetic probes where permitted. Check membership, recent posts/chat, board replay, attachment contents, private-note isolation and denied sibling/admin URLs. Verify old browser/panel cookies and pending codes cannot authenticate. Record elapsed recovery time, recovery point and any data deliberately lost after that point. Reopen traffic only after these checks and operator approval.

## Reproduce the synthetic engineering rehearsal

```bash
LABADDA_RECOVERY_TESTS=1 scripts/verify.sh
```

The configured disposable test role needs CREATEDB and PostgreSQL 16 clients on PATH. The recovery test seeds synthetic content in `LABADDA_TEST_DATABASE_URL`, creates a uniquely named empty target, dumps/restores real PostgreSQL and assets, verifies content and authorization through the application, and drops only its own target in cleanup. Never point the test suite at site state. Without `LABADDA_RECOVERY_TESTS=1`, that integration test is explicitly skipped; filesystem/configuration recovery tests still run. CI enables it and installs the required clients. CI execution itself must be confirmed from the CI service; a local pass is not a claim that hosted CI completed.

Physical panel acceptance, a site TLS/service rehearsal, verified off-host backup transport, retention policy and pilot-owner approval remain separate gates.

## Serialized operational wrapper

The [operations guide](development/operations.md#managed-backup-and-upgrade-installed-sites)
describes the default-plan-only lifecycle wrapper for service quiescence, consistent
backup, upgrade sequencing and durable fail-closed journals. Restore remains the
explicit isolated-target procedure above; the wrapper never rewinds live data.
