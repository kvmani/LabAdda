# Site operations implementation

Read [deployment](../DEPLOYMENT.md), [releases](../RELEASES.md) and
[recovery](../RECOVERY.md) before changing operational boundaries. The stdlib
`scripts/operations.py` validates the exact site schema in
`deploy/site.example.json`, renders configuration into an exclusive review
directory and performs bounded health/readiness probes. Tests:
`backend/tests/test_operations.py`. Release integrity/installation stays in
`scripts/release.py`; database and asset consistency stays in
`backend/labadda/recovery.py`. Do not duplicate either protocol.

## Render and inspect

Copy the example outside the checkout, substitute site values, then run:

```sh
python3 scripts/operations.py --site /etc/labadda/site.json render --out /tmp/labadda-review
```

Rendering does not install files, create identities/databases, change traffic or
activate a service. Review `plan.json`, `service.conf` and `nginx.conf`; provision
its directory ownership/modes before installation. Keep releases publicly
traversable/readable for nginx, assets private to the runtime account, and
operations/backups private to the operator. The runtime must not own its release
code, environment file, TLS key or service/proxy configuration. Install the service
as `labadda-<instance>.service`. The generated service is a **system** service,
separate from the older user-service example. `ProtectHome=true` requires a
`/srv`-style deployment rather than a home-directory release.

Install proxy configuration inside nginx's `http` context, run `nginx -t` and
`systemd-analyze verify` against the installed unit before enabling either.
The template reserves a dedicated HTTPS virtual host; multiple instances sharing
one host need a separately reviewed combined proxy configuration. Site certificates,
CA distribution, DNS, PostgreSQL roles, disk encryption, host patching and off-host
storage are site inputs, not generated secrets or an implied successful deployment.

The server-level maintenance marker is `<root>/traffic/maintenance`. The directory
must be searchable by nginx (0755); the marker can be 0644 and contains no secrets.
It blocks all new requests on this virtual host, including assets and sockets.
Existing sockets require stopping the service. Remove the marker only after
migration, direct readiness and operator review; then verify the TLS route:

```sh
python3 scripts/operations.py --site /etc/labadda/site.json probe --direct
python3 scripts/operations.py --site /etc/labadda/site.json probe --ca-file /etc/labadda/site-ca.crt
```

Probes require exact JSON status, refuse redirects, ignore ambient HTTP proxies,
verify TLS certificates and time out each endpoint after ten seconds. A passing
probe verifies liveness/schema readiness only; it does not replace authenticated
workflows, asset checks, WebSocket checks, restore drills or site acceptance.

## Next runnable slices

Add serialized/journaled maintenance and backup orchestration around the existing
recovery CLI, then safe upgrade orchestration with fail-closed maintenance. Never
infer that a local digest proves publisher identity or that a successful backup
proves recovery/off-host durability. Restore remains isolated and never changes
traffic. Dedicated simulation orchestration follows the collaboration test map.

## Managed backup and upgrade (installed sites)

`scripts/lifecycle.py` wraps the existing trusted release/recovery protocols.
It supports **installed-site** backups/upgrades, not initial database provisioning.
Run it from a verified operator-owned tool directory, with system-service privileges
and PostgreSQL16 clients in `/usr/bin`. No shell is evaluated. It accepts a strict
unquoted environment-file subset: unique allowlisted `LABADDA_*=value` lines,
no whitespace, quotes or backslashes; URL-encode database credential punctuation.
The file must be operator/root-owned mode0600 or stricter. Values must match the
site's instance, prefix, private assets, current frontend, unique cookie and HTTPS
origin. The subprocess environment excludes ambient Python, pip, PostgreSQL and
loader selectors. The exact libpq TLS allowlist is `PGSSLMODE=verify-full`, `PGSSLROOTCERT`
and optionally paired `PGSSLCERT`/`PGSSLKEY` absolute paths. No ambient connection
selectors are retained. Install certificates where both the runtime and operator
can read them; keep client keys private.

Provision the layout from `plan.json` first. Every ancestor, installed release,
venv, tool and configuration file must be controlled by the trusted operator,
not writable by the runtime account; root runs must not execute untrusted code.
Only the assets directory is runtime-writable. This is a host prerequisite, not a
claim that the tool can safely run in an attacker-owned filesystem tree.

```sh
# Install/verify the candidate first using release.py and its independently trusted digest.
# Preview: reads configuration and verifies installed payloads; does not stop anything.
python3 scripts/lifecycle.py --site /etc/labadda/site.json upgrade \
  --expected-current previous --expected-schema 0025 --candidate candidate
# After review, schedule downtime and stop every external CLI/worker writer:
python3 scripts/lifecycle.py --site /etc/labadda/site.json upgrade \
  --expected-current previous --expected-schema 0025 --candidate candidate \
  --apply --external-writers-stopped
# Backup only: leaves maintenance ON and service STOPPED after success.
python3 scripts/lifecycle.py --site /etc/labadda/site.json backup \
  --expected-current candidate --expected-schema 0025 --apply --external-writers-stopped
```

The nonblocking instance lock serializes invocations. Private fsynced JSONL journals
in `<root>/operations` record phase, release/schema and backup manifest digest,
never credentials/content or raw subprocess errors. The operator must separately
retain trusted digests and transfer backups off host using approved encrypted
storage with verification; local backup success does not prove off-host durability.

Apply rejects changed current code/schema or existing maintenance. It publishes a
durable marker, stops the system service, verifies `MainPID=0` and inactive/failed,
then creates a consistent verified backup through the active release's CLI. The
external-writer flag is an operator attestation, not process discovery. Upgrade
then runs candidate migrations, observes schema, validates/switches code atomically,
starts the service, polls loopback readiness (60-second window plus at most
20 seconds for the final bounded probe), removes maintenance and probes HTTPS. The TLS
probe uses the OS trust store: install the site CA there first. There is necessarily
a short open-traffic interval for the final external probe; a failure immediately
reinstates maintenance. These probes do not replace authenticated acceptance.

Any failed/interrupted command retains maintenance; command deadlines terminate
its child process group. A host/process crash can leave an incomplete last phase:
inspect the journal and live schema/pointer before doing anything. Do not replay
migrations or infer rollback safety from a missing completion record. No automatic
schema downgrade, data rewind, backup deletion or failure resume is implemented.

After a successful backup-only operation, verify the journal/backup, start the
service (`systemctl start labadda-<instance>`), run `probe --direct`, remove the
maintenance marker, then run the TLS probe. If anything is unconfirmed, retain or
reinstate the marker. For failed upgrades use [recovery](../RECOVERY.md): same-schema
code rollback requires actual observed-schema proof; otherwise restore into a
new isolated target with a separately trusted manifest digest. Never restore over
the live database. Initial deployment still follows [deployment](../DEPLOYMENT.md)
and `release.py`: create dedicated empty DB/assets, migrate exactly once while
isolated, preflight, switch, start and qualify before opening traffic.

Tests `backend/tests/test_lifecycle.py` inject failures at stop, stopped-state,
backup, migration and both probes, test lock contention, private configuration,
stale plans, redaction and subprocess deadlines. Real systemd boot, persistence,
permissions, site TLS, off-host transfer and full DR timing remain site gates.
