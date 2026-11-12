---
title: Moving to a new server
summary: Rebuild the site on a new server from a verified backup and switch over once it has been checked.
audience: operator
screen: none
updated: 2026-11-12
---

## What this is for

Use this page when the server is being replaced. You prepare the new server, restore the latest backup there as an isolated copy, check it, and only then switch people over. The old server stays untouched until the site owner is satisfied.

Replace `<tools>`, `<site-name>`, `<version>`, `<bundle-folder>`, `<trusted-digest>` and `<schema>` with your own values.

## Before you start

- The new server has the same operating system version, PostgreSQL 16, nginx and the site certificate, prepared as the deployment guide supplied with the release describes.
- You have a recent backup of the old site, checked and copied to the new server, and its manifest digest from a separate trusted record.
- You have the release archive and its checksum. Use the same release as the old server, or one the backup supports.
- Agree a time with the site owner. Anything written on the old site after the backup is not carried over, so close the old site for the final backup.

## Steps

1. On the old server, take a final backup as in [Taking and checking backups](backup.md). Keep the old server running but closed to people.
2. On the new server, install the release as in [Installing LabAdda on a new server](install.md), up to the point of rendering the service files. Create the empty database and keep the uploaded-files folder absent. Do not set up the first administrator: they come with the backup.
3. Check the copied backup against the trusted digest:

   ```bash
   cd /srv/labadda/<site-name>/current/backend
   ../venv/bin/python -m labadda.cli verify-backup <bundle-folder> --manifest-sha256 <trusted-digest>
   ```

4. Restore it as an isolated copy, preview first, as in [Restoring from a backup](restore.md):

   ```bash
   python3 <tools>/scripts/commission.py --site /etc/labadda/<site-name>.site.json restore \
     --candidate <version> --bundle <bundle-folder> --manifest-sha256 <trusted-digest>
   python3 <tools>/scripts/commission.py --site /etc/labadda/<site-name>.site.json restore \
     --candidate <version> --bundle <bundle-folder> --manifest-sha256 <trusted-digest> \
     --apply --isolated-target
   ```

5. Take a verified backup of the restored site, then switch to the release and start the service:

   ```bash
   python3.12 <tools>/scripts/release.py activate --instance /srv/labadda/<site-name> \
     --release <version> --database-schema <schema> --writers-quiesced --backup-verified
   sudo systemctl start labadda-<site-name>
   python3 <tools>/scripts/operations.py --site /etc/labadda/<site-name>.site.json probe --direct
   ```

6. Sign in with a test account and check recent posts, chat, a board and an attachment. Run the doctor. Point the site address at the new server only when everything passes.
7. Set up the nightly backups on the new server as in [Taking and checking backups](backup.md).

## What happens next

People sign in again, because sessions are not carried over. Administrators who had read-only operational access must be given it again. Keep the old server and its database unchanged until the site owner confirms the new site is correct.

## If something goes wrong

- The restore refuses to run: read the message. Common causes are a digest that does not match, a database that is not empty, or a folder that already exists.
- The check finds missing recent content: the backup was taken too early. Take a new final backup on the old server and restore again into a new empty database.
- The new site fails its checks: leave people on the old server and follow [When the site is down](site-is-down.md).

## Related

- [Restoring from a backup](restore.md)
- [Installing LabAdda on a new server](install.md)
- [Taking and checking backups](backup.md)
