---
title: Taking and checking backups
summary: Set up the nightly backup, take one now, check that it can be trusted and keep copies safely.
audience: operator
screen: none
updated: 2026-11-12
---

## What this is for

A backup is a copy of the database and all uploaded files at one moment. LabAdda makes one every night from a timer and records the result so the Backups page in Administration can show it. A backup you have not checked, or that exists only on the same server, is not a safe backup.

Replace `<site-name>`, `<tools>`, `<bundle-folder>` and `<trusted-digest>` with your own values. The site is unavailable for the few minutes each backup takes, so choose a quiet hour.

## Before you start

- The settings file names a status folder (`LABADDA_STATUS_DIR`) that you own and the service account can read. The backup result is written there.
- You have the two backup timer files supplied with the release. Copy them to `/etc/systemd/system/` and edit the tool folder and the hour inside them.
- No other LabAdda job runs at that hour.

## Steps

1. Switch on the nightly timer and make the first backup now:

   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now labadda-backup@<site-name>.timer
   sudo systemctl start labadda-backup@<site-name>.service
   ```

2. Run the doctor. Its backup line should now pass:

   ```bash
   cd /srv/labadda/<site-name>/current/backend
   ../venv/bin/python -m labadda.cli doctor --env-file /etc/labadda/<site-name>.env
   ```

3. Check a finished backup again whenever you want to be sure. You need the manifest digest, which you recorded in a separate, trusted place when the backup was made:

   ```bash
   cd /srv/labadda/<site-name>/current/backend
   ../venv/bin/python -m labadda.cli verify-backup <bundle-folder> --manifest-sha256 <trusted-digest>
   ```

4. The timer keeps the newest seven backups. See what it would remove without removing anything:

   ```bash
   python3 <tools>/scripts/lifecycle.py --site /etc/labadda/<site-name>.site.json prune-backups --keep 7
   ```

5. Copy the backups off the server by your approved process, and keep them private. They contain everything people wrote. Practise a restore on a spare machine from time to time.

## What happens next

Each night the site closes briefly, a verified backup is taken, the site reopens, and the result is recorded. Administrators can read it on the **Backups** page. It shows times, sizes and results only.

## If something goes wrong

- The **Backups** page says Unknown or Unavailable: run the first-backup command from step 1, read the log with `journalctl -u labadda-backup@<site-name>`, and run the doctor.
- The site stays closed after a backup: the backup did not pass its check. Do not reopen it by hand. Read the log first and follow [When the site is down](site-is-down.md).
- You are not sure the copy is complete: run the check in step 3 on the copy, not only on the original.

## Related

- [Restoring from a backup](restore.md)
- [Reading the Backups page](../admin/backups-page.md)
- [Backup problems](../troubleshooting/health-backups.md)
