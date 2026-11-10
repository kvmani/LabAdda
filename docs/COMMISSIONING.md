# Empty-site initialization and isolated disaster recovery

Use [deployment](DEPLOYMENT.md), [recovery](RECOVERY.md) and the
[operations guide](development/operations.md) first. `scripts/commission.py` is a
plan-first operator wrapper for **new isolated** instances. It never provisions
roles, executes seed/reset, changes the current pointer, starts a service, deletes
content or opens traffic. Tests: `backend/tests/test_commission.py`.

Provision the reviewed system-service layout first: trusted operator-owned code,
verified installed candidate, configuration and TLS; separate empty PostgreSQL16
database/least-privilege role; public traffic directory; private operator state.
Use a system unit installed but **stopped**. Ensure there are no external writers,
unmanaged processes or routed user traffic; `--isolated-target` attests this.
The site file and private environment must point to this target, including its
unique DB, assets, instance, cookie and HTTPS origin. These inputs must not be a
copy of the live service's configuration without changing its storage/identity.
The tool confirms no current pointer and no objects in any non-system database namespace;
it does not discover every external process or network route.

## First deployment

Create `<root>/assets` empty/private and owned by the runtime account. Install the
candidate with the existing release tool and its independently trusted digest.
Preview then apply with the same arguments:

```sh
python3 scripts/commission.py --site /etc/labadda/new-site.json initialize --candidate candidate
python3 scripts/commission.py --site /etc/labadda/new-site.json initialize --candidate candidate \
  --apply --isolated-target
```

Apply serializes against other lifecycle operations, publishes durable maintenance,
checks the stopped service, verifies the empty DB, runs candidate migrations once,
and checks the actual schema against the installed candidate. Completion remains
**isolated**. No production backup is required for a proven empty first install.
On failure, inspect its fsynced private journal and DB; do not retry by removing the
marker or erasing partially initialized content. An operator must classify and
recover the failed attempt first.

## Disaster recovery rehearsal / recovery target

Provision a **different empty database** and keep `<root>/assets` absent. Transfer
a verified backup securely to an isolated location. Obtain its manifest SHA256
through an independently trusted channel, never by trusting the transferred
bundle's own checksum file. Use a release compatible with the bundle's schema.

```sh
python3 scripts/commission.py --site /etc/labadda/recovery-site.json restore \
  --candidate candidate --bundle /srv/recovery-input/bundle --manifest-sha256 TRUSTED_SHA256
# After plan review, repeat with --apply --isolated-target.
```

The wrapper binds the supplied digest before executing the existing recovery CLI.
Recovery verifies the full bundle/private snapshot, rejects the source DB name and
nonempty targets, restores transactionally, validates asset/preview references,
revokes copied sessions/tokens/delegations and pauses copied jobs. Failed targets
remain quarantined for inspection; never activate a partial target or restore over
the live DB. Full recovery evidence must include actual execution, elapsed time,
recovery point, separately verified off-host copy and authenticated content checks.
A successful preview or unit test does not establish RPO/RTO.

## Controlled activation after either operation

The wrapper leaves maintenance enabled and does not select code. Before activation,
verify restored file ownership/modes for the runtime user (restores run as the
operator), DB role access, systemd restrictions and certificate trust. The runtime
must be able to access assets while being unable to modify release/venv/config.
Keep backups, journals and secrets inaccessible to nginx and the runtime account.
Create a consistent verified backup of the now initialized/restored isolated target
through the candidate's recovery CLI before activation, and retain its trusted
manifest digest. Then use `release.py activate --instance ROOT --release candidate
--database-schema HEAD --writers-quiesced --backup-verified` with the actual
verified backup and observed schema. Both attestations must be true; do not use a
placeholder flag or claim an existing-data backup for an empty pre-migration DB.
The pointer switch does not open traffic.

Start the service, poll direct readiness, verify protected authenticated flows,
assets and WebSockets, then remove maintenance and probe the TLS route. Immediately
reinstate maintenance on failure. Site acceptance requires representative load,
manual accessibility/device testing, restart persistence and a timed isolated
restore. Retain the old host/database unchanged until the owner accepts the
recovery target. Do not treat successful code preparation as deployment approval.
