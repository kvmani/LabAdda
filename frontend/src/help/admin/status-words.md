---
title: What the status words mean
summary: Learn the six words used for every check, and why Unknown is never the same as Healthy.
audience: administrator
screen: none
updated: 2026-11-11
---

## What this is for

Every check and tile in the administration area uses exactly one of six words, each with an icon. The words are the same everywhere so you can learn them once.

## Steps

1. **Healthy** means the check ran recently and everything is within its limits.
2. **Degraded** means something works but is outside its limits, such as a slow database. People may notice slowness.
3. **Unavailable** means the thing is not working or is below a safe minimum, such as a failed backup. People may be unable to work.
4. **Stale** means the figure is too old to trust. The last check may have been fine, but it is not recent enough to say so now.
5. **Unknown** means there is nothing to judge yet, such as no backup report. It is never shown as healthy and never as zero.
6. **Not supported** means this installation cannot measure that thing, such as a certificate report that is not provided. It is left out of the overall state.
7. The overall state is the worst of the checks, ignoring those marked **Not supported**.

## What happens next

Nothing changes when you read a status. Acknowledging an event on the **Events** page records that you have seen it, but it never makes a check turn green.

## If something goes wrong

If a check you expect to be healthy says **Unknown**, open its **What to do** page; it says what the server needs to report.

## Related

- [Reading system health](system-health.md)
