---
title: Live connection problems
summary: What a Live connections problem means, what people notice and what to do.
audience: administrator
screen: none
updated: 2026-11-11
---

## What this is for

The Live connections card counts open live links, such as boards and chat, and the people seen in the last five minutes. It is **Degraded** when messages waiting to be delivered pile up beyond the limit, and **Unavailable** when they pile up far beyond it.

Event codes: `connections.degraded`, `connections.unavailable`. Event codes are shown on the **Events** page.

What people notice: Chat messages and board strokes arrive late or not until the page is reloaded. Saved work is not lost.

## Steps

1. Choose **Check now** and watch whether the waiting count falls.
2. If many people have the whiteboard open, ask some to close it for a few minutes.
3. Ask people to reload their page if live updates stopped.

## What happens next

The server checks again every 15 seconds. When the check passes, the event closes by itself and **System health** shows **Healthy**.

## If something goes wrong

Call the operator if the backlog does not fall within ten minutes.

## Related

- [Reading system health](../admin/system-health.md)
- [Working with events](../admin/events.md)
