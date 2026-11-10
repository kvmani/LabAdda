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
