---
title: Reading system health
summary: See whether the server is working, which check needs attention, and what to do about it.
audience: administrator
screen: none
updated: 2026-11-11
---

## What this is for

The **System health** page shows ten checks of the server that runs LabAdda: the application, the database, file storage, live connections, background jobs, response time, sign-in, backups, the server computer and the site certificate. It shows times, counts and sizes only. It never shows anyone's messages, notes, file names or board pictures.

## Steps

1. Choose **System health** in the administration menu.
2. Read the band at the top. It gives the worst state of all the checks and says how many need attention.
3. Find any card whose word is not **Healthy**. Each card gives the figure, one sentence about it, and **Checked** with how long ago the server measured it.
4. Choose **What to do** on that card to open the page that explains the problem.
5. Choose **Check now** if you want to see the latest figures straight away. The page also refreshes itself every 15 seconds while it is on screen, and stops while the tab is hidden.
6. Look at the chart on a card to see the last 24 hours. Choose **View as table** to read the same figures as numbers.

## What happens next

When a check turns bad, the server records an event and you can read it on the **Events** page. When the check recovers, the event closes by itself.

## If something goes wrong

If every card says **Unknown**, the server has only just started. Wait a minute and choose **Check now**. If the page says it could not be refreshed, the figures shown are old; the card words change to **Stale** after a minute. Ask the person who looks after the server to check that LabAdda is running.

## Related

- [What the status words mean](status-words.md)
- [Working with events](events.md)
