---
title: Application problems
summary: What a Application problem means, what people notice and what to do.
audience: administrator
screen: none
updated: 2026-11-11
---

## What this is for

The Application card shows the version, how long the server has been running, and whether the database layout matches this release. It is **Degraded** when the database is behind or ahead of the software, which happens after an upgrade that was not finished or a rollback that did not restore the database.

Event codes: `application.degraded`. Event codes are shown on the **Events** page.

What people notice: Some screens may fail with an error, or saving may be refused, until the layout matches.

## Steps

1. Choose **System health** and read the sentence on the **Application** card. It says whether the layout is behind or ahead.
2. Do not restart the server repeatedly. That does not change the layout.
3. Ask the person who looks after the server to finish the upgrade, or to switch back to the matching release.

## What happens next

The server checks again every 15 seconds. When the check passes, the event closes by itself and **System health** shows **Healthy**.

## If something goes wrong

Call the operator straight away; nothing you can do in the web app changes the database layout.

## Related

- [Reading system health](../admin/system-health.md)
- [Working with events](../admin/events.md)
