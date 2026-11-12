---
title: Publishing a site notice
summary: Show one short message to everyone who is signed in, for example before planned maintenance.
audience: administrator
screen: none
updated: 2026-11-11
---

## What this is for

A site notice is one short message shown at the top of every page for everyone who is signed in. Use it for things people need to plan around, such as maintenance that pauses saving. It is plain text only, up to 280 characters, and it removes itself at the end time.

## Before you start

Only administrators can publish a notice. Board-only screens do not show it. Decide when it should start and end. Times use the time zone of the computer you are using.

## Steps

1. Open **Administration** and choose **Settings**.
2. In **Site notice**, type the message in **Notice text**.
3. Choose **Notice level**: Information for general news, Warning for anything that interrupts work.
4. Set **Show from**, or leave it empty to start now.
5. Set **Show until**. The notice must end in the future.
6. Check the preview, then choose **Publish notice**.

## What happens next

People see the notice within a minute, between the start and end times. The change is recorded in the audit trail with who made it and when, but the audit trail keeps only the length of the text, not the text. Publishing again replaces the notice. Choose **Remove notice** to take it down early.

## If something goes wrong

- The page says someone else changed the notice. Reload the page to see their version, then publish again if you still want to.
- The text is refused. Remove line breaks and unusual symbols, and keep it within the limit.
- The end time is refused. It must be later than the start time and in the future.

## Related

- [Reading the settings page](settings.md)
- [Reading the Backups page](backups-page.md)
