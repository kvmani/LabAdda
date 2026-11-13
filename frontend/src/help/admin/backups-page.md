---
title: Reading the Backups page
summary: See when the last backup finished, whether it was checked, and what to do when it is late.
audience: administrator
screen: none
updated: 2026-11-11
---

## What this is for

The **Backups** page in Administration shows the last backup that the server recorded. LabAdda does not make backups itself. A timer set up by the person who looks after the server makes them and leaves a small receipt, and this page reads that receipt. It shows times, sizes and results only, never file names or folder paths.

## Before you start

Administrators can open the page, and so can people who have been given read-only operational access. Nobody can change anything here.

## Steps

1. Open **Administration** and choose **Backups**.
2. Read the coloured word under **Latest backup**. Healthy means a verified backup finished within the last 26 hours.
3. Read **Finished**, **Size** and **Verification**. A backup is only trusted when verification says Passed.
4. Read **Kept at** to see the short name of the place the backup was copied to.
5. Choose **Check again** to read the receipt again.

## What happens next

If the word is Degraded, the last good backup is more than 26 hours old. If it is Stale, it is more than 50 hours old. If it is Unavailable, the last backup failed or could not be verified. Tell the person who looks after the server, and ask them to run a backup and read the log. **Next scheduled backup** and **Last restore practice** say Not recorded because the receipt does not carry them.

## If something goes wrong

- The word is Unknown and the page says no backup has been recorded. Nothing proves a backup exists. Ask for the set-up to be finished before relying on this site.
- The word is Unknown and the page says the record cannot be read. The receipt was edited or damaged. Ask for a new backup to be run.
- The word is Unknown and the page says the last backup is dated in the future. The server clock is wrong.

## Related

- [Reading the settings page](settings.md)
- [Broadcast messages](broadcast.md)
