---
title: When the disk is filling up
summary: Find what is using the space and free it safely without touching what people have saved.
audience: operator
screen: none
updated: 2026-11-12
---

## What this is for

Backups, uploaded files and the database all grow over time. When the disk is nearly full, uploads fail and, in the end, the database and the whole site stop. This page shows how to free space without deleting anything people wrote.

Replace `<site-name>` and `<tools>` with your own values.

## Before you start

- Nothing people have written or uploaded may be deleted to make space. If the only way to free space is to remove content, stop and ask the site owner.
- Before removing any old backup, make sure at least one recent backup has been copied off this server.

## Steps

1. See which disk is full and how much room is left:

   ```bash
   df -h
   ```

2. Run the doctor. It reports free space for the uploaded-files folder:

   ```bash
   cd /srv/labadda/<site-name>/current/backend
   ../venv/bin/python -m labadda.cli doctor --env-file /etc/labadda/<site-name>.env
   ```

3. List the biggest folders under the site's root folder to see whether backups, releases or uploads are the cause:

   ```bash
   sudo du -sh /srv/labadda/<site-name>/* /srv/labadda-backups/<site-name>/* | sort -h
   ```

4. If old backups take the space, preview which ones would be removed to keep only the newest few. Nothing is removed without the apply option:

   ```bash
   python3 <tools>/scripts/lifecycle.py --site /etc/labadda/<site-name>.site.json prune-backups --keep 7
   ```

   Read the list. If it is right, run it again with `--apply`. Use a smaller number only when a recent copy is safe elsewhere.
5. If old installed releases take the space, keep the release the site is running and the one before it. Ask the supplier of the release before removing any others.
6. If uploaded files are the cause, tell the site owner. Administrators can see how much space each workspace uses; the people who own the workspaces decide what to remove.
7. Run `df -h` again to confirm the space is back.

## What happens next

Free space of more than a fifth of the disk gives you months of room. Plan a bigger disk if the files keep growing. The doctor warns you again when space runs low.

## If something goes wrong

- The disk is full and the site has stopped: free space first, with step 4 or 5, then start the service and run the checks in [When the site is down](site-is-down.md).
- The preview lists a backup you want to keep: copy it somewhere safe first, or raise the number to keep.
- You are tempted to delete files in the uploads folder: do not. Files there are referenced by people's posts, chat and notes.

## Related

- [Taking and checking backups](backup.md)
- [Looking after workspace storage](../stewards/workspace-storage.md)
- [When the site is down](site-is-down.md)
