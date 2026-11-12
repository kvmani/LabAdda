---
title: Reading the settings page
summary: See the limits this site runs with and who changes them.
audience: administrator
screen: none
updated: 2026-11-11
---

## What this is for

The **Settings** page lists the limits this site is running with, in plain words: how long people stay signed in, how large a file can be, how long usage figures are kept, and similar. It also holds the site notice and the time-limited operational access list. The limits are shown for information. They never include passwords, folder paths, server names or other private details.

## Before you start

Only administrators can open this page. People with read-only operational access can open Backups but not Settings.

## Steps

1. Open **Administration** and choose **Settings**.
2. Use **Site notice** to publish a message to everyone, as described in the notice guide.
3. Read each group of limits, such as Signing in and Files and storage. Each line gives the value, what it means, and who changes it.
4. Use the operational access section lower on the page to give someone read-only access for a limited time.

## What happens next

Every limit on this page says Changed by the operator in the site configuration file. That means you cannot change it here. Ask the person who looks after the server, and tell them which line you want changed and why. The new value appears on this page after the server is restarted.

## If something goes wrong

- A value looks wrong for your office. Ask the operator to review it. Nothing on this page can be broken by looking at it.
- The page does not load. Choose Try again. If it keeps failing, tell the operator.

## Related

- [Publishing a site notice](site-notice.md)
- [Reading the Backups page](backups-page.md)
