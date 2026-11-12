---
title: Reading the Overview
summary: See at a glance whether everything is all right, what needs you, and where to go to fix it.
audience: administrator
screen: none
updated: 2026-11-12
---

## What this is for

The **Overview** is the first page of Administration. It answers two questions: is everything all right, and what needs me? It shows statuses, counts, sizes and times only. It never shows anyone's messages, notes, file names or board pictures, and it never shows how much one person used the system.

## Before you start

Administrators can open it, and so can people who have been given read-only operational access. The page refreshes by itself every 15 seconds while the tab is open, and says how long ago it was updated. If it cannot refresh, it keeps the last figures, tells you so, and after a minute marks them **Stale**.

## Steps

1. Open **Administration**. The coloured band at the top is the overall state: the worst of the system checks. **Unknown** means some checks have no figures yet, so the site is not confirmed healthy.
2. Read **Needs attention**. It lists the most serious item first. Each entry has an **Open** link to the page where you can deal with it, and **What to do** when there is a guide. If nothing needs attention the page says so plainly.
3. Read the six tiles: people active today, people signed in now, live connections, storage used, last backup and open events. Choose a tile's name to open the page behind the figure. The small line shows the last seven days.
4. Read the two charts: people active each day, and the slowest response time of each day.
5. Choose **Check now** to read everything again.

## What happens next

Nothing changes when you read the Overview. Acknowledge or resolve events on the **Events** page, and appoint a steward or Head for a unit on the **Organisation** page. The entry leaves the list once the cause has been fixed.

An event about something that already has its own entry is not listed twice. A unit without an active steward or Head is listed as a warning, because nobody is answering for it.

## If something goes wrong

- A tile says **Not measured**. Nothing has been recorded yet, which is not the same as zero. Figures appear a few minutes after people start using the site.
- A tile says **Fewer than 5**. To protect privacy, a figure about people is hidden while fewer than five people stand behind it. The same rule applies on the Activity page.
- A day is missing from a chart. The server recorded nothing that day, so the chart shows a gap instead of zero.
- The page says the figures are out of date. The server may be busy or unreachable. Choose **Check now**, and if it still fails tell the person who looks after the server.

## Related

- [What the status words mean](status-words.md)
- [Reading system health](system-health.md)
- [Reading the Backups page](backups-page.md)
- [Reading the Activity page](activity-page.md)
- [Events](events.md)
