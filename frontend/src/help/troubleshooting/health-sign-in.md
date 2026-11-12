---
title: Sign-in problems
summary: What a Sign-in problem means, what people notice and what to do.
audience: administrator
screen: none
updated: 2026-11-11
---

## What this is for

The Sign-in card counts successful and failed sign-ins over 15 minutes. It is **Degraded** when many more than usual fail. This can mean people have forgotten passwords, or someone is guessing them.

Event codes: `sign_in.degraded`. Event codes are shown on the **Events** page.

What people notice: People cannot sign in, or are slowed down by the limit on repeated attempts.

## Steps

1. Read the card: how many signed in and how many failed.
2. If a few people are affected, open **People** and issue them a new password link.
3. Open **Audit** and look at recent sign-in security entries for the names and times involved. They show names and times, not passwords.
4. If you do not recognise the activity, tell the operator.

## What happens next

The server checks again every 15 seconds. When the check passes, the event closes by itself and **System health** shows **Healthy**.

## If something goes wrong

Call the operator if failures keep climbing, or if you suspect someone is guessing passwords.

## Related

- [Reading system health](../admin/system-health.md)
- [Working with events](../admin/events.md)
