---
title: Server problems
summary: What a Server problem means, what people notice and what to do.
audience: administrator
screen: none
updated: 2026-11-11
---

## What this is for

The Server card shows the memory LabAdda uses, how busy the computer is and how much of its memory is in use, read from the computer itself. It is **Degraded** when any of them is above its limit. It shows **Not supported** when the computer does not report these figures.

Event codes: `server.degraded`. Event codes are shown on the **Events** page.

What people notice: Everything may feel slow, and in the worst case the server restarts.

## Steps

1. Read the sentence on the card to see which figure is high.
2. Wait a few minutes; a busy spell often passes.
3. Ask people to avoid heavy uploads while it is high.

## What happens next

The server checks again every 15 seconds. When the check passes, the event closes by itself and **System health** shows **Healthy**.

## If something goes wrong

Call the operator if it stays **Degraded** for more than an hour.

## Related

- [Reading system health](../admin/system-health.md)
- [Working with events](../admin/events.md)
