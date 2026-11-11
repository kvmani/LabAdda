# Operator quickstart

For the person who looks after one LabAdda site on its Ubuntu 24.04 server. Five steps, in
order: install, first administrator, doctor, backup, upgrade. Every step says where the full
rules are; read those before the first real install. Replace `<site-name>`, `<version>` and
`<tools>` with your own values (the site name is a short lowercase word such as `main`;
`<tools>` is the folder holding the verified `scripts/` you run from). Run commands as the
operator account, not as root unless a line starts with `sudo`.

Every tool here shows a plan first and changes nothing until you add `--apply`. None prints a
password. Never paste real addresses, passwords or tokens into tickets or chat.

## 1. Install

You need a release archive and its checksum, delivered separately ([releases](RELEASES.md)), and
the server prepared as in [deployment](DEPLOYMENT.md): PostgreSQL 16, nginx, your site certificate,
an empty database and role for this site.

1. Describe the site in `/etc/labadda/<site-name>.site.json` (copy `deploy/site.example.json`)
   and the private settings in `/etc/labadda/<site-name>.env` (copy `deploy/labadda.env.example`,
   mode 0600). The settings include `LABADDA_STATUS_DIR`, the folder where backup results are
   recorded; create it owned by you and readable by the service account.
2. Check the archive and install it, then render the service and web-server files for review:

   ```bash
   python3.12 <tools>/scripts/release.py verify labadda-<version>.tar.gz --sha256 <trusted-digest>
   python3.12 <tools>/scripts/release.py install labadda-<version>.tar.gz \
     --sha256 <trusted-digest> --instance /srv/labadda/<site-name>
   python3 <tools>/scripts/operations.py --site /etc/labadda/<site-name>.site.json render \
     --out ~/labadda-review
   ```

3. Review and install the rendered files, create the empty folders it lists, then set up the
   database and activate with the commissioning steps in [commissioning](COMMISSIONING.md#first-deployment).
   Start the service only when that guide says to.

## 2. Create the first administrator

With the settings loaded for the command (they are plain `KEY=value` lines, so `env` can read
them), from the installed release:

```bash
cd /srv/labadda/<site-name>/current/backend
env $(grep -v '^#' /etc/labadda/<site-name>.env) ../venv/bin/python -m labadda.cli create-admin <username> \
  --display-name "<Full Name>"
```

It prints a one-time activation token. Give it to that person privately. They open
`https://<site-address>/<prefix>/activate`, enter it and choose a password. The token is not
stored anywhere you can read it again; run the command for a new one if it expires.

## 3. Run the doctor

```bash
cd /srv/labadda/<site-name>/current/backend
../venv/bin/python -m labadda.cli doctor --env-file /etc/labadda/<site-name>.env
```

Each line says what was checked, whether it is fine, and for a problem, how to fix it: settings,
database and schema, uploaded-files folder and free space, the service, the address people use,
the certificate, the backup record and the time zone. The exit code is 0 only when nothing failed
(add `--json` for a machine-readable report). Fix problems from the top, run it again, and repeat
until it is clean. It changes nothing and prints no passwords. Until the first backup exists, the
backup line will fail: that is expected, go to step 4. Run the doctor again after every upgrade.

## 4. Set up backups

Backups run every night from a timer and record their result in `LABADDA_STATUS_DIR`, where the
doctor (and later the administrator console) reads it. **The site is unavailable for the few
minutes a backup takes.** Copy `deploy/systemd/labadda-backup@.service` and
`labadda-backup@.timer` to `/etc/systemd/system/`, edit the tool path and the hour, confirm no
other LabAdda job runs then, and enable it:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now labadda-backup@<site-name>.timer
sudo systemctl start labadda-backup@<site-name>.service   # first backup now
```

Run the doctor again: the backup line should pass. The timer keeps the newest seven backups.
Check what it would remove with `lifecycle.py ... prune-backups --keep 7` (no `--apply`). Local
copies are not a safe backup on their own: copy them off the server by your approved process and
practise a restore on a spare machine ([recovery](RECOVERY.md#scheduled-backups-and-the-status-file)).

## 5. Upgrade

1. Verify and install the new release next to the old one (step 1.2, same commands, new
   `<version>`). Nothing changes for users yet.
2. Preview. This takes no action and shows the plan:

   ```bash
   python3 <tools>/scripts/lifecycle.py --site /etc/labadda/<site-name>.site.json upgrade \
     --expected-current <old-version> --expected-schema <old-schema> --candidate <version>
   ```

3. Choose a quiet time, tell people, make sure no other LabAdda job is running, and repeat the
   same command with `--apply --external-writers-stopped`. It puts the site into maintenance,
   takes a verified backup, applies the update, restarts, checks the site and reopens it. If
   anything fails it keeps the site in maintenance: do not retry, follow
   [recovery](RECOVERY.md) and the [operations guide](development/operations.md#managed-backup-and-upgrade-installed-sites).
4. Run the doctor.

For the full set of rules see [deployment](DEPLOYMENT.md), [releases](RELEASES.md),
[recovery](RECOVERY.md) and the [operations guide](development/operations.md).
