---
title: Background job problems
summary: What a Background jobs problem means, what people notice and what to do.
audience: administrator
screen: none
updated: 2026-11-11
---

## What this is for

The Background jobs card shows how long ago the server last finished its regular round of work, such as reminders, file cleanup and usage figures, and how many runs failed in the last hour. It is **Degraded** after two minutes without a finished round or after repeated failures, and **Unavailable** after ten minutes.

Event codes: `jobs.degraded`, `jobs.unavailable`. Event codes are shown on the **Events** page.

What people notice: Reminders arrive late, uploads that were never attached are not cleaned up, and charts stop filling in.

## Steps

1. Choose **Check now**. A long cleanup can make one round slow without being a fault.
2. Note whether the failed runs count is going up.
3. Do not ask people to repeat their work. Reminders that were due are sent once the scheduler is running again.

## What happens next

The server checks again every 15 seconds. When the check passes, the event closes by itself and **System health** shows **Healthy**.

## If something goes wrong

Call the operator if it is **Unavailable**, or **Degraded** for more than half an hour.

## Related

- [Reading system health](../admin/system-health.md)
- [Working with events](../admin/events.md)
