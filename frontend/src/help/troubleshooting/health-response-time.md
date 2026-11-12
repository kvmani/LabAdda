---
title: Response time problems
summary: What a Response time problem means, what people notice and what to do.
audience: administrator
screen: none
updated: 2026-11-11
---

## What this is for

The Response time card shows how fast the server answered over the last five minutes, and how many requests ended in a server error. It is **Degraded** when the slowest 5 percent take more than a second, or more than 2 percent of requests failed. With no requests it shows **Unknown**.

Event codes: `response_time.degraded`. Event codes are shown on the **Events** page.

What people notice: Pages feel slow, or some actions show an error message and need to be repeated.

## Steps

1. Choose **Check now**; the figures cover the last five minutes and settle after a short busy period.
2. Check the **Database** and **Server** cards. A slow database or a busy computer is the usual cause.
3. Ask people to avoid very large uploads for a while if the server is busy.

## What happens next

The server checks again every 15 seconds. When the check passes, the event closes by itself and **System health** shows **Healthy**.

## If something goes wrong

Call the operator if it stays **Degraded** for more than half an hour.

## Related

- [Reading system health](../admin/system-health.md)
- [Working with events](../admin/events.md)
