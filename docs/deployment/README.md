# Deploying LabAdda — which setup are you in?

Every setup runs the **same code with no local edits**. Machines are air-gapped and reach only the
office's internal **Ubuntu (apt), Python (pip) and npm mirrors**. Releases travel as GitHub's
**"Source code (zip)"** plus its SHA-256, exactly like project_management_software (PM); no git is
used on these machines.

| | A. Dedicated VM | B. Beside PM on its VM | C. Windows 11 |
| --- | --- | --- | --- |
| Purpose | Production | Production | Trying features in a browser only |
| Address | `https://<hostname>/` or `http://<IP>/` | `http://<IP>/labadda/` | `http://127.0.0.1:8000/` |
| `WEB_ACCESS` answer | `https` or `dedicated-http` | `shared-http` | not used |
| nginx | Own `conf.d/labadda-main.conf` | One include line in PM's site ([details](pm-coexistence.md)) | none |
| Services | systemd **user** services of an account, like PM | same | `scripts\windows\serve-dev.ps1` |
| Data | PostgreSQL 16 database `labadda_main` | same, beside PM's SQLite files | disposable fixture database |

## What the server needs (A and B)

Ubuntu 24.04 with, from the internal apt mirror: `postgresql-16 postgresql-client-16 nginx
python3.12-venv openssl nodejs npm` (Ubuntu's Node.js 18 builds the screens). The installer refuses
to run if one is missing when given `--skip-os-packages`.

Mirrors: `PIP_INDEX_URL` in the answers file (required) is the internal Python mirror for both the
build and the installed release. The screens are built with `npm ci` as the operator who typed
`sudo`, so npm uses that person's `~/.npmrc` — the same setting PM's builds use — unless
`NPM_REGISTRY` is given. The ZIP installer requires an internal registry for both package managers. Verified: the build works with Ubuntu 24.04's own Node.js 18.19 and npm 9.2
(npm prints engine warnings for test-only packages; they are not used on a server). Every pinned package is at least **30 days old**
when a release is cut (`scripts/check_dependency_age.py`, no exceptions), so a mirror that missed
a few nightly syncs still has everything.

## Services: user scope, like PM

`SERVICE_SCOPE=user` (the default for new installs) runs `labadda-main.service` and the nightly
`labadda-backup@main.timer` in the systemd **user** manager of `SERVICE_USER` (default: the account
that ran `sudo`, e.g. the same one that runs PM's `ipms-*` units). Lingering is enabled so they run
from boot. That account owns `/srv/labadda/main` and `/srv/labadda-backups/main`; root keeps only
the database password and the installer answers in `/etc/labadda/secrets` and `*.install.conf`.

```bash
sudo -u <account> XDG_RUNTIME_DIR=/run/user/$(id -u <account>) systemctl --user status labadda-main
```

A site installed before 0.1.0 has no `service_scope` in `/etc/labadda/main.site.json` and stays a
**system** unit (`systemctl status labadda-main`) through upgrades; nothing moves on its own.

## First install from the zip

On the connected PC: publish the GitHub release, download **Source code (zip)**, run
`sha256sum LabAdda-X.Y.Z.zip` (or `Get-FileHash` on Windows) and write the hash down separately.
Copy the zip to the server, then:

```bash
unzip -q LabAdda-X.Y.Z.zip
cp LabAdda-X.Y.Z/deploy/office-pilot/install.conf.example ~/labadda-install.conf   # edit it; chmod 600
sudo bash LabAdda-X.Y.Z/deploy/install.sh --zip LabAdda-X.Y.Z.zip --sha256 <HASH> \
  --answers ~/labadda-install.conf --skip-os-packages --dry-run
sudo bash LabAdda-X.Y.Z/deploy/install.sh --zip LabAdda-X.Y.Z.zip --sha256 <HASH> \
  --answers ~/labadda-install.conf --skip-os-packages
```

The installer checks the hash and that the zip is GitHub's archive of a LabAdda commit, checks
Python, Node.js, npm, disk and mirrors, builds the verified bundle under
`/var/tmp/labadda-builds/<commit>/` from the mirrors, then installs it (database, settings, nginx,
services, first backup, doctor). The first administrator's activation code prints once.

## Upgrade from the zip

```bash
unzip -q LabAdda-X.Y.Z.zip
sudo bash LabAdda-X.Y.Z/deploy/upgrade.sh --zip LabAdda-X.Y.Z.zip --sha256 <HASH> --dry-run
sudo bash LabAdda-X.Y.Z/deploy/upgrade.sh --zip LabAdda-X.Y.Z.zip --sha256 <HASH>
```

In order: zip hash and identity; build prerequisites and mirrors; **sanity checks of the running
site** — release active and healthy on its own port and at its address, not in maintenance,
PostgreSQL and `nginx -t` fine, disk room for the pre-upgrade backup and the new release
(`--dry-run` stops here); build beside the live site; then close the site, **verified backup**,
migrate, switch, start, health checks, reopen. If health fails, the old release is put back
automatically when the database allows it; otherwise the site stays closed and the script says
which backup to restore. Data is never rewound silently.

Daily commands: `sudo labadda-status`, `sudo labadda-backup-now --copy-to <drive>`,
`sudo labadda-reattach-nginx` (setup B, after PM rewrote its nginx file).
`sudo labadda-admin` lists every routine job under one command: `status [--json]`, `check`
(exit 0 when running, answering, open and backed up in the last 36 hours, for cron or
monitoring), `doctor`, `logs [LINES]`, `restart`, `backup`, `backups`, `upgrade`, `restore`,
`reattach-nginx` and `support-report [DIR]` (status, checks and versions in one file, no
secrets or content, to send when asking for help).

## C. Windows 11 (testing only)

No installer, no services, fictional data. **Delete the old folder and unzip the new release**
(never unzip on top: files removed in a release, such as a replaced database migration, would
linger and break startup), then run `scripts\windows\setup-dev.ps1` and
`scripts\windows\serve-dev.ps1`. pip and npm use your
`pip.ini` / `.npmrc` mirror settings. See the [Windows guide](../development/windows-testing.md).

## Proving a change before it reaches a server

```bash
git archive --format=zip --prefix=LabAdda-test/ HEAD > /tmp/LabAdda-test.zip   # what GitHub publishes
sudo scripts/rehearse-rollout.sh --zip /tmp/LabAdda-test.zip                      # A, https, user scope
sudo scripts/rehearse-rollout.sh --zip /tmp/LabAdda-test.zip --dedicated-http     # A, IP only
sudo scripts/rehearse-rollout.sh --zip /tmp/LabAdda-test.zip --shared-http        # B, PM's real nginx file
sudo scripts/rehearse-rollout.sh OLD-BUNDLE --upgrade-zip /tmp/LabAdda-test.zip   # upgrade a live 0.0.2 site
```

Each run uses a scratch prefix, real PostgreSQL and real nginx, and removes what it made.
Not covered by a rehearsal: a real systemd user manager and lingering (a stand-in runs the units),
apt installing packages, and the office mirrors themselves.
