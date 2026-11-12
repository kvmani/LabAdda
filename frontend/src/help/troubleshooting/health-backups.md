---
title: Backup problems
summary: What a Backups problem means, what people notice and what to do.
audience: administrator
screen: none
updated: 2026-11-11
---

## What this is for

The Backups card reads the report left by the operator's backup job. It is **Degraded** when the last backup is more than 26 hours old, and **Unavailable** when it is more than 50 hours old, failed, or did not verify. It is **Unknown** when no report exists, which does not mean backups exist.

Event codes: `backups.degraded`, `backups.unavailable`. Event codes are shown on the **Events** page.

What people notice: Nothing, until something goes wrong and there is nothing recent to restore.

## Steps

1. Choose **Backups** in the administration menu to see the last report: time, size and whether it was checked.
2. If the report is missing, ask the person who looks after the server whether the backup schedule is set up.
3. Do not assume a backup exists because the page is quiet.

## What happens next

The server checks again every 15 seconds. When the check passes, the event closes by itself and **System health** shows **Healthy**.

## If something goes wrong

Call the operator the same day when backups are **Unavailable**, and at the first chance when they are **Unknown**.

## Related

- [Reading system health](../admin/system-health.md)
- [Working with events](../admin/events.md)
