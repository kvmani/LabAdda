---
title: File storage problems
summary: What a File storage problem means, what people notice and what to do.
audience: administrator
screen: none
updated: 2026-11-11
---

## What this is for

The File storage card shows free space and free file slots on the disk that holds uploads and board pictures, compared with the reserve the operator set. It is **Degraded** when free space is within 20 percent above the reserve, and **Unavailable** below it.

Event codes: `file_storage.degraded`, `file_storage.unavailable`. Event codes are shown on the **Events** page.

What people notice: Uploads and snapshots may start failing, and the database may stop saving when the disk is full.

## Steps

1. Read the card to see how much space is left and the reserve.
2. Open **Storage** in the administration menu to see where the space is going. It shows sizes and counts only.
3. Ask stewards of the largest workspaces to remove files they no longer need. LabAdda never deletes anyone's files for you.
4. Ask the operator to add disk space if the trend on the 24-hour chart keeps falling.

## What happens next

The server checks again every 15 seconds. When the check passes, the event closes by itself and **System health** shows **Healthy**.

## If something goes wrong

Call the operator at once when it is **Unavailable**, because a full disk can stop the whole server.

## Related

- [Reading system health](../admin/system-health.md)
- [Working with events](../admin/events.md)
