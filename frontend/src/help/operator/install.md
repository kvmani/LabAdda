---
title: Installing LabAdda on a new server
summary: Put a release on a prepared server, create the first administrator and check that everything is healthy.
audience: operator
screen: none
updated: 2026-11-12
---

## What this is for

This page takes you from a prepared Ubuntu server to a running LabAdda site with one administrator who can sign in. It is for the person who looks after the server, not for everyday users.

Every tool below shows a plan first and changes nothing until you add `--apply`. None of them prints a password. Replace `<site-name>`, `<version>`, `<tools>` and `<trusted-digest>` with your own values: the site name is a short lowercase word such as `main`, and `<tools>` is the folder that holds the verified operator scripts you were given with the release.

## Before you start

- You have the release archive and its checksum, delivered to you separately. A checksum that arrived next to the archive proves nothing about who made it.
- The server already has PostgreSQL 16, nginx, your site certificate, and an empty database and database account for this site. The deployment guide supplied with the release lists these.
- You are signed in as the operator account, not as the root account.
- Never paste real addresses, passwords or activation codes into tickets or chat.

## Steps

1. Describe the site in `/etc/labadda/<site-name>.site.json` and the private settings in `/etc/labadda/<site-name>.env`, copying the example files supplied with the release. Keep the settings file readable only by you. Create the folder named by `LABADDA_STATUS_DIR` and make it readable by the service account; backup results are recorded there.
2. Check the archive, install it, and write the service and web-server files into a review folder:

   ```bash
   python3.12 <tools>/scripts/release.py verify labadda-<version>.tar.gz --sha256 <trusted-digest>
   python3.12 <tools>/scripts/release.py install labadda-<version>.tar.gz \
     --sha256 <trusted-digest> --instance /srv/labadda/<site-name>
   python3 <tools>/scripts/operations.py --site /etc/labadda/<site-name>.site.json render \
     --out ~/labadda-review
   ```

3. Read the files in the review folder, install them where the deployment guide says, and create the empty folders the plan lists. Keep the service stopped.
4. Set up the empty database. Preview first, read the plan, then repeat with the two extra options. They are your promise that nothing else is using this database.

   ```bash
   python3 <tools>/scripts/commission.py --site /etc/labadda/<site-name>.site.json initialize \
     --candidate <version>
   python3 <tools>/scripts/commission.py --site /etc/labadda/<site-name>.site.json initialize \
     --candidate <version> --apply --isolated-target
   ```

5. Make a first verified backup of the new, still empty site as the commissioning guide describes, then switch to the new release. Use the schema number that step 4 printed:

   ```bash
   python3.12 <tools>/scripts/release.py activate --instance /srv/labadda/<site-name> \
     --release <version> --database-schema <schema> --writers-quiesced --backup-verified
   ```

6. Start the service and open the site to people only when the commissioning guide says the checks have passed:

   ```bash
   sudo systemctl start labadda-<site-name>
   python3 <tools>/scripts/operations.py --site /etc/labadda/<site-name>.site.json probe --direct
   ```

7. Create the first administrator. The command prints a one-time activation code. Give it to that person privately.

   ```bash
   cd /srv/labadda/<site-name>/current/backend
   env $(grep -v '^#' /etc/labadda/<site-name>.env) ../venv/bin/python -m labadda.cli create-admin <username> \
     --display-name "<Full Name>"
   ```

   The person opens the site address followed by `/activate`, enters the code and chooses a password.
8. Run the doctor and fix anything it reports, from the top, until it is clean:

   ```bash
   cd /srv/labadda/<site-name>/current/backend
   ../venv/bin/python -m labadda.cli doctor --env-file /etc/labadda/<site-name>.env
   ```

9. Set up nightly backups as described in [Taking and checking backups](backup.md).

## What happens next

The administrator signs in and works through the setup checklist in Administration. The doctor's backup line fails until the first backup exists. That is expected.

## If something goes wrong

- A step stops with a message: read it, fix the one thing it names and run the same command again. Do not delete half-created databases or folders to start over; ask for help first.
- The activation code has run out: run step 7 again for a new one.
- The doctor reports a problem you do not understand: keep its output (it contains no passwords) and ask the supplier of the release.

## Related

- [Upgrading to a new release](upgrade.md)
- [Taking and checking backups](backup.md)
- [Getting a status report](status-report.md)
