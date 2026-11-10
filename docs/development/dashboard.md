# Daily personal collaboration overview

Read CT-14/T51 and the [API contract](../API.md#c5-daily-overview).

`api/dashboard.py` selects active owner-private tasks plus shared assignments under
current readable sources; orders before its25-row window; collects10 dated owner
notes,10 notifications resolved through existing source policy and10 unread spaces.
It rechecks identity/grants after serialization, filters protected rows and suppresses
shared pagination signals on change. No private-note/author/source-reference content
is added to site usage reports. No aggregate site-wide counts are claimed.

`Dashboard.tsx` at /today (My day in desktop/mobile navigation) labels limits and
calendar timezone. Refresh clears stale results; a failed read is unavailable,
not empty data. Scope generations and socket revocation invalidate held responses;
notifications open only after an authorized API response. Activity is a refresh
hint, not a total or automatic archive. Owner notes and personal tasks survive
loss of an unrelated shared source. Existing home-workspace landing is preserved.

LABADDA_TIMEZONE defaults UTC; config.py now rejects missing/invalid IANA zones.
Deployment needs installed system tzdata; Asia/Kolkata is supported for local review.
Date-only tasks compare against this advertised calendar, not a browser UTC cast.

Checks: test_dashboard, assignment/group regressions and e2e/dashboard.mjs. Dashboard
has no new migration. User alert preferences are the following C5 slice. Physical/
representative-site/manual accessibility acceptance remains separate.
