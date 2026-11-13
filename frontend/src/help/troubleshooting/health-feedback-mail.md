---
title: Feedback e-mail problems
summary: What a Feedback e-mail problem means, what people notice and what to do.
audience: administrator
screen: none
updated: 2026-11-13
---

## What this is for

The Feedback e-mail card counts feedback messages waiting to be e-mailed to the administrators and those that could not be sent. It is **Degraded** when any message failed or has waited more than 30 minutes. It shows **Not supported** when e-mail is not set up; feedback is still saved on the **Feedback** page.

Event codes: `feedback_mail.degraded`. Event codes are shown on the **Events** page.

What people notice: nothing. Their feedback is saved either way. Administrators miss the e-mail copy.

## Steps

1. Open **Feedback** in the console and look at the e-mail column.
2. Read the reason shown for a failed message.
3. Ask the person who looks after the server to fix the mail settings, then choose **Send e-mail again**.

## What happens next

Waiting messages are retried automatically. The event closes when the check passes.

## If something goes wrong

Read the messages on the **Feedback** page directly until e-mail works.

## Related

- [Reading system health](../admin/system-health.md)
- [Working with events](../admin/events.md)
