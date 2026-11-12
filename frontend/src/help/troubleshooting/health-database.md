---
title: Database problems
summary: What a Database problem means, what people notice and what to do.
audience: administrator
screen: none
updated: 2026-11-11
---

## What this is for

The Database card shows how quickly the database answers, how many of its connections are in use and how large it is. It is **Degraded** when answers take more than a quarter of a second or most connections are in use, and **Unavailable** when the database does not answer at all.

Event codes: `database.degraded`, `database.unavailable`. Event codes are shown on the **Events** page.

What people notice: Pages load slowly, saving is slow, or everything fails with an error. When the database is unavailable nobody can sign in or save.

## Steps

1. Choose **Check now** to see whether it was a short blip.
2. Read the card sentence. Slow answers often follow a large import or a backup running at the same time.
3. If connections are nearly all in use, ask people to close extra tabs and wait a few minutes.
4. If the database is **Unavailable**, do not try to fix it from the web app. Note the time and the **Events** entry.

## What happens next

The server checks again every 15 seconds. When the check passes, the event closes by itself and **System health** shows **Healthy**.

## If something goes wrong

Call the operator if the database is **Unavailable** for more than a few minutes, or **Degraded** for more than an hour.

## Related

- [Reading system health](../admin/system-health.md)
- [Working with events](../admin/events.md)
