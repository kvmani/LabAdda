---
title: Certificate problems
summary: What a Certificate problem means, what people notice and what to do.
audience: administrator
screen: none
updated: 2026-11-11
---

## What this is for

The Certificate card shows how many days remain on the certificate that makes the address start with https. It is **Degraded** with less than 30 days left, **Unavailable** with less than 7 or once it has expired, and **Stale** when the operator's report has not been refreshed for three days. It shows **Not supported** when no report is provided.

Event codes: `certificate.degraded`, `certificate.unavailable`, `certificate.stale`. Event codes are shown on the **Events** page.

What people notice: When it expires, browsers warn people that the connection is not private, and some refuse to open the site.

## Steps

1. Read the days left on the card.
2. Tell the person who looks after the server the number of days left. Renewing the certificate is their job.
3. Tell staff not to click through browser warnings once the certificate has expired.

## What happens next

The server checks again every 15 seconds. When the check passes, the event closes by itself and **System health** shows **Healthy**.

## If something goes wrong

Call the operator as soon as it is **Degraded**, and immediately when it is **Unavailable**.

## Related

- [Reading system health](../admin/system-health.md)
- [Working with events](../admin/events.md)
