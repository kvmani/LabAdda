---
title: Setting up a new site
summary: Use the live checklist to see what a new installation still needs, and where to do each job.
audience: administrator
screen: none
updated: 2026-11-12
---

## What this is for

The **Setting up this site** page lists the jobs a new installation needs, such as a second administrator, units, people and backups. Each line is checked against the real state of the site every time the page loads, so it can never be ticked by hand.

## Before you start

You need to be a site administrator. Usage readers cannot open this page.

## Steps

1. Choose **Help for administrators** in the administration menu. The checklist opens.
2. Read the heading, for example "3 of 7 done", and then each line. A line shows **Done**, **Not done** or **Unknown**.
3. For a line that is not done, choose **Open the page** to go to the screen where you fix it.
4. Choose **Read the help** to open the page that explains the job.
5. After you have made a change, choose **Check again**. The page also refreshes by itself.

The lines are: a second administrator, organisation units created, people added, a steward or Head for every unit, backups reporting healthy, the site time zone confirmed, and a test restore recorded.

## What happens next

A line turns **Done** only when the site shows that it is true, for example when two active administrators exist. If you later undo the work, the line goes back to **Not done**.

## If something goes wrong

- A line says **Unknown**. The site cannot tell yet. The backups line stays Unknown until the person who looks after the server has set up backups. The test restore line stays Unknown until a restore test has been recorded. Ask that person; do not treat Unknown as done.
- The time zone line says **Not done**. Only the person who looks after the server can set the time zone. Open **Settings** to see the zone in use, then ask them to set it.
- "Your administration access changed". Reload the page; your access was reduced.
- The list will not load. Choose **Try again**.

## Related

- [Adding a person](add-a-person.md)
- [Importing a staff list](import-a-staff-list.md)
- [Who looks after a unit](unit-administrators.md)
- [Reading the Backups page](backups-page.md)
- [Reading the settings page](settings.md)
