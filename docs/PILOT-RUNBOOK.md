# Pilot runbook

For the site owner and the person who looks after the server during the supervised pilot. It
puts the existing guides in order and lists what to prepare, what to run, what to watch and what
to send back when something goes wrong. It adds no new rules: where a step needs detail it links
to the guide that owns it. Names below (`main`, `ana.owner`) are made up; use your own.

Replace `<site-name>` (a short lowercase word such as `main`), `<version>`, `<tools>` (the folder
with the verified `scripts/`) and `<trusted-digest>` with your own values. Every operator tool
shows a plan first and changes nothing until you add `--apply`. Never paste real passwords,
addresses or activation codes into tickets or chat.

## 1. Before the pilot

| Need | Detail |
| --- | --- |
| Server | One Ubuntu **24.04 LTS** x86-64 virtual machine with Python 3.12, PostgreSQL 16 (with its `pg_dump` and `pg_restore` clients) and nginx, all from your internal mirror. A release built on any other system is refused. |
| Size | Suggested start, not measured on your site: 4 processors, 8 GB memory, 100 GB disk. The release is about 35 MB and one installed copy about 205 MB; plan room for several releases, uploaded files and seven local backups. The health screen warns when free disk drops below 5 GiB. |
| Certificate | A certificate and key from your internal authority for the address people will type, trusted by the office browsers. Put them where `deploy/site.example.json` points. Renewal: the in-app operator help "Renewing the certificate". |
| Time zone | An IANA name such as `Europe/London`. Set it in `LABADDA_TIMEZONE`. Days, reports and schedules follow it; the setup checklist stays "not done" until it is chosen. |
| Database | An empty database and its own login for this site. |
| Off-server copy | A place to copy backups to by your approved process. A backup that only lives on the server is not a safe backup. |
| People | Who is the operator, who are the administrators (at least two), who answers when something fails. |

Settings live in `/etc/labadda/<site-name>.env` (mode 0600, copied from `deploy/labadda.env.example`;
every setting the server reads is listed there) and the site description in
`/etc/labadda/<site-name>.site.json`. Use `LABADDA_ENV=pilot`: it makes the fixture commands refuse
to run, which protects real data.

## 2. Install and first sign-in

Follow [the operator quickstart](OPERATOR-QUICKSTART.md) steps 1 to 3 and
[commissioning](COMMISSIONING.md#first-deployment). In order:

```bash
python3.12 <tools>/scripts/release.py verify labadda-<version>.tar.gz --sha256 <trusted-digest>
python3.12 <tools>/scripts/release.py install labadda-<version>.tar.gz \
  --sha256 <trusted-digest> --instance /srv/labadda/<site-name>
python3 <tools>/scripts/operations.py --site /etc/labadda/<site-name>.site.json render --out ~/labadda-review
python3 <tools>/scripts/commission.py --site /etc/labadda/<site-name>.site.json initialize --candidate <version>
python3 <tools>/scripts/commission.py --site /etc/labadda/<site-name>.site.json initialize \
  --candidate <version> --apply --isolated-target
python3.12 <tools>/scripts/release.py activate --instance /srv/labadda/<site-name> \
  --release <version> --database-schema <schema> --writers-quiesced --backup-verified
sudo systemctl start labadda-<site-name>
python3 <tools>/scripts/operations.py --site /etc/labadda/<site-name>.site.json probe --direct
```

Read the rendered files in `~/labadda-review` and install them before the `initialize --apply` step,
as the quickstart says. Then create the first administrator and check the installation:

```bash
cd /srv/labadda/<site-name>/current/backend
env $(grep -v '^#' /etc/labadda/<site-name>.env) ../venv/bin/python -m labadda.cli create-admin ana.owner \
  --display-name "Ana Owner"
../venv/bin/python -m labadda.cli doctor --env-file /etc/labadda/<site-name>.env
```

The first command prints a one-time token. Give it to Ana privately; she opens
`https://<site-address>/activate`, enters it and chooses a password. Run the doctor until every
line is fine, except the backup line, which passes after the first backup (section 4).

## 3. First day in the app

Sign in as the first administrator, then open **Administration**, **Help for administrators**
(`/admin/help/setup`). The setup checklist reads the real state of the site, so it cannot be
ticked by hand. Work through it in this order:

1. Create a **second administrator** (People, Add a person). Never rely on one account.
2. Create the **organisation units** (Organisation chart) and note each unit's code.
3. **Import the staff list**: People, Import staff list. Save the spreadsheet as CSV UTF-8, check
   the report, give a reason, apply, print the activation slips. The help page "Importing a staff
   list" has the columns and the common messages.
4. Make sure every unit has a **steward or head**.
5. Take the first backup and confirm **Backups** shows it (section 4).
6. Confirm the **time zone** line is done.
7. The **test restore** line stays "unknown" until a restore is recorded; see the limits below.

## 4. The daily check, and backups

Each morning an administrator opens **Overview** and **Backups**. Both show times, sizes and
results only. Overview "unknown" or "stale" means not measured; it never means healthy. Backups
must say the last backup finished and was verified within the last 26 hours. If not, run the
doctor and see section 7.

Install the nightly timer once ([recovery](RECOVERY.md#scheduled-backups-and-the-status-file)):

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now labadda-backup@<site-name>.timer
sudo systemctl start labadda-backup@<site-name>.service
```

The site is unavailable for the few minutes a backup takes. The timer keeps the newest seven local
backups; copy them off the server yourself. **Test a backup** on a spare machine or a spare
database, never over the live one. With a finished bundle and its manifest digest, taken from the
backup record and not from the bundle:

```bash
cd /srv/labadda/<site-name>/current/backend
../venv/bin/python -m labadda.cli verify-backup <bundle-folder> --manifest-sha256 <trusted-digest>
```

then restore to a new empty database with a different name, following the in-app help
"Restoring from a backup" and [recovery](RECOVERY.md#restore-without-exposing-traffic) (it uses
`commission.py ... restore`, or `labadda restore <bundle-folder> --manifest-sha256 <trusted-digest>
--isolated-target` with `LABADDA_RESTORE_DATABASE_URL` and a new `LABADDA_ASSET_DIR` set). Sign in to the copy, look at
recent posts and chat, and note how long it took. Everyone is signed out by a restore.

## 5. Upgrading during the pilot

Follow the in-app operator help "Upgrading to a new release" ([quickstart step 5](OPERATOR-QUICKSTART.md#5-upgrade)):
verify and install the new release beside the old one, preview, then apply in a quiet hour with
nobody else running a LabAdda job.

```bash
python3 <tools>/scripts/lifecycle.py --site /etc/labadda/<site-name>.site.json upgrade \
  --expected-current <old-version> --expected-schema <old-schema> --candidate <version>
python3 <tools>/scripts/lifecycle.py --site /etc/labadda/<site-name>.site.json upgrade \
  --expected-current <old-version> --expected-schema <old-schema> --candidate <version> \
  --apply --external-writers-stopped
```

It puts the site into maintenance, takes a verified backup, migrates once, switches the code,
checks the site and reopens it. Run the doctor afterwards. If any step fails, the site stays in
maintenance. Do not retry; send the report in section 7.

## 6. Rolling back

Switching back to the previous code is allowed only when the database schema still matches that
release exactly; the tool refuses otherwise:

```bash
python3.12 <tools>/scripts/release.py rollback --instance /srv/labadda/<site-name> \
  --release <previous-version> --database-schema <schema> --writers-quiesced --backup-verified
```

An upgrade that changed the schema cannot be rolled back this way, and migrations are never run
backwards on a site with data (each refuses while its rows exist). Recovery is then a restore of
the backup taken at the start of the upgrade into a new empty database ([section 4](#4-the-daily-check-and-backups)),
checked before anyone is let in. Nothing rewinds data automatically.

## 7. When something goes wrong

Stop, leave the site in maintenance if it is, and send back, using no passwords or message text:

1. The doctor report: `../venv/bin/python -m labadda.cli doctor --env-file /etc/labadda/<site-name>.env --json`
   (from `/srv/labadda/<site-name>/current/backend`).
2. The status report described in the operator help "Getting a status report", with the
   `operations.py ... probe --direct` result.
3. The release version and schema number, the time it started, and the last thing done.
4. For a failed upgrade or backup, the newest journal file name and its last line (not the secrets
   it does not contain).

## 8. Known limits for this pilot

- **Do not appoint unit administrators yet.** The feature is delivered but awaits the owner's
  decisions; use site administrators only.
- The **test restore** setup item stays "unknown": the app has no way to record a restore yet.
  Keep your own note of when you rehearsed one.
- The **whiteboard canvas stays white in the dark theme**; drawings remain readable.
- Backups pause the site for a few minutes each night.
- Not proven on a real host yet: systemd units, nginx with your certificate, and an off-server
  restore. The Ubuntu rehearsal (plan card D1) must record these before real people rely on the site.
