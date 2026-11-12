---
title: Working with events
summary: Read the problems the server noticed, acknowledge them with a note, and see them close by themselves.
audience: administrator
screen: none
updated: 2026-11-11
---

## What this is for

The **Events** page lists problems the server noticed, newest first. A problem raises one event, even if it stays bad for hours; the **Times** column counts how often it was seen again. Usage readers can read events but cannot change them.

## Steps

1. Choose **Events** in the administration menu.
2. Use **Status**, **Severity** and **Where** to narrow the list. The choices stay in the address, so you can share the filtered view.
3. Choose an event's description to open its details.
4. Choose **Open the guide for this problem** to read what it means and what to do.
5. Type a **Note** saying what you know or what you will do, then choose **Acknowledge**. The event moves to **Acknowledged**, with your name and note.
6. Choose **Mark as resolved** only after the cause is fixed. The server refuses while the check behind the event is still failing.
7. Choose **Older events** to page back, and **Newest events** to return.

## What happens next

An open or acknowledged event closes by itself when its check turns **Healthy** again. If the same check fails again later, a new event is raised.

## If something goes wrong

If **Mark as resolved** says the problem is still present, the check has not passed yet. Fix the cause and wait for the next check, which runs every 15 seconds. If the list will not load, choose **Try again**.

## Related

- [Reading system health](system-health.md)
- [What the status words mean](status-words.md)
