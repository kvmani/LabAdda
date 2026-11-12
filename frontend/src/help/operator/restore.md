---
title: Restoring from a backup
summary: Bring a backup back on a separate empty database, check it, and only then let people in.
audience: operator
screen: none
updated: 2026-11-12
---

## What this is for

A restore rebuilds the site from a backup. LabAdda never restores over a running site. It always builds a second, isolated copy that nobody can reach until you have checked it. This is also how you practise recovery and how you move to a new server.

Replace `<tools>`, `<recovery-site>`, `<version>`, `<bundle-folder>` and `<trusted-digest>` with your own values.

## Before you start

- You have the backup folder, copied to a private place on the server doing the restore.
- You have its manifest digest from a separate, trusted record. Never take the digest from the folder you are checking.
- There is a new, empty database with a different name, and the folder for uploaded files does not exist yet. The recovery site has its own site description file and settings.
- A release that matches the backup is installed, as in [Upgrading to a new release](upgrade.md). Nothing is receiving traffic and no other LabAdda job is running.

## Steps

1. Preview. This checks the backup and prints the plan without changing anything:

   ```bash
   python3 <tools>/scripts/commission.py --site /etc/labadda/<recovery-site>.site.json restore \
     --candidate <version> --bundle <bundle-folder> --manifest-sha256 <trusted-digest>
   ```

2. When the plan is right, run it again with the two extra options. They say that the target is isolated and that nothing else is using it:

   ```bash
   python3 <tools>/scripts/commission.py --site /etc/labadda/<recovery-site>.site.json restore \
     --candidate <version> --bundle <bundle-folder> --manifest-sha256 <trusted-digest> \
     --apply --isolated-target
   ```

3. Check the restored site before anyone is told about it: sign in with a test account, look at a workspace's recent posts and chat, open a board and an attachment, and confirm that a person cannot open another team's workspace.
4. Everyone's old sign-ins and unused activation codes are removed by the restore. People sign in again. Administrators who had read-only operational access must be given it again.
5. Switch to the restored site only when you and the site owner agree it is correct, following the activation step in [Installing LabAdda on a new server](install.md). Write down how long the restore took and what time the backup was taken, so you know what was lost.

## What happens next

The restored site keeps the content up to the backup time. Anything written after that time is not in it. The tool leaves traffic closed and does not choose which release runs.

## If something goes wrong

- The tool refuses to start: it found a problem with the backup, the digest, the target database or the folder. Read the message, fix that one thing, and run the preview again.
- The restore fails after the database was filled. Keep that database exactly as it is for inspection, and try again with a new empty database and a folder that does not exist. Never empty or reuse it.
- You cannot tell whether the backup is complete: run the check in [Taking and checking backups](backup.md) first.

## Related

- [Taking and checking backups](backup.md)
- [Moving to a new server](moving-to-a-new-server.md)
- [When the site is down](site-is-down.md)
