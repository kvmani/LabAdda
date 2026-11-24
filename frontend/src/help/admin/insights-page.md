---
title: Reading the Insights page
summary: See which features are growing or fading, and how fast and reliable LabAdda is, to decide where to focus.
audience: administrator
screen: none
updated: 2026-11-24
---

## What this is for

The **Insights** page helps you decide where to put effort as LabAdda grows. **Feature trends** shows how the use of each feature changes week by week and sorts features into those to focus on, those to look at more closely, and those that may be simplified or retired. **Performance** shows how quickly LabAdda answers, how often a request fails with a server error, and how many sign-ins fail, for the whole site and for each feature area. The page shows counts and timings only. It never shows messages, notes, file names, board pictures or who did what. Usage readers can see this page too, but cannot change anything.

## Steps

1. Choose **Insights** in the administration menu.
2. On **Feature trends**, choose a **Period** of 8 weeks, 12 weeks, 6 months or 12 months. Weeks start on Monday in the site time zone.
3. Read the people figures at the top: active people per week, **Reach** (the share of enabled accounts active in a week) and **Return rate** (how many of a week's active people come back on an average day).
4. Read **What to do next**. Each feature is compared over the last four complete weeks with the four weeks before them. **Growing**, **New** and **Core** features are listed under **Focus here**; **Declining** features under **Look closer**; **Dormant** and **Unused** features under **Candidates to simplify or retire**.
5. Read the charts and the **Feature momentum** table. Choose a column heading to sort by it, for example by **Share of activity**.
6. Choose **Performance** and a **Period** of 24 hours, 7 days, 30 days or 90 days.
7. Read the tiles. A tile with a coloured edge is outside its target. The targets are the response time and error rate limits used by System health.
8. Read the response time, server error and request charts, then the table of **Feature areas, slowest first** to see where people wait the longest.

## What happens next

The figures refresh by themselves every minute while the page is on screen. Nothing on this page changes LabAdda. Use what you learn to plan training, ask colleagues about a feature that is losing use, or report a slow area to the server operator.

## If something goes wrong

If a figure says **Not measured**, nothing was collected for it in that period, which is not the same as no use. If the trends view says **Hidden to protect privacy**, every week had fewer than five active people, so its figures could point to one person. **Not enough data** means fewer than two measured weeks on one side of the comparison; wait a few weeks or choose a longer period. A sudden rise in response time or server errors is worth reporting to the server operator together with the period and the feature area.

## Related

- [Reading the Activity page](activity-page.md)
- [Reading system health](system-health.md)
- [What the status words mean](status-words.md)
