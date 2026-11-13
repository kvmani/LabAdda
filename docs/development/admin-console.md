# Admin console implementation

Read [A1](../plan/admin.md#a1--admin-console-shell-and-navigation),
[AD-01–02](../ADMIN-CONSOLE-V1.md) and [API A1](../API.md#a1--console-access-and-navigation-ad-0102).

## Access foundation (implemented)

`policy.console_sections` returns current sections from administrator status or
an unexpired usage-reader grant; no workspace membership implies console access.
`deps.require_console(section, admin_only=...)` checks normal sessions and rejects
explicit panel markers. Read-only delegates may use six metadata sections; writes
and the existing privileged storage endpoints remain administrator-only.

`GET /admin/console` returns section names and `read_only`, without content. Existing
admin, governance, usage, grant-management and inventory endpoints use the dependency
while preserving their old payloads and permission/error boundaries. Legacy internal
usage-reader checks delegate to the same policy. No new role/schema is introduced.

Checks: `tests/test_console.py`, `test_capabilities.py`, existing feature negative
cases. The console never authorizes access to posts, notes, chat, files or boards.

## Web delivery

`pages/Admin.tsx` is the lazy console entry; `features/admin/AdminConsole.tsx`
registers nested routes inside `AdminLayout`. Navigation is derived from
`GET /admin/console`; ordinary members redirect home, delegates see only their
six sections and cannot mount People/Organisation/Audit/Settings/Help. A frame
remount per history entry plus generation invalidation prevents delayed access
responses from rendering a prior route. Failed lookups have a retry state. `AdminBoundary` contains failed console code
downloads/rendering so workspace navigation survives; explicit reload retries the
failed module. The browser check blocks both Vite preload and import requests.

Existing controls move without new data/actions: `BasicAdministration` holds
People/Organisation; administrators get `Governance` at storage, delegates get
the existing read-only `Operations` view; `Settings` holds `UsageReaders`.
`/operations` redirects to storage. Future sections use honest placeholders.
These basic controls retain their existing markup until P/U4; no new change
protocol or quota enforcement is implied. Panel layout is unchanged.

Browser checks: `e2e/admin-console.mjs` (root/prefix, role navigation, aliases,
refresh, held/reordered lookup, failed lookup retry, grant/revocation, mobile and
axe). Registered in the full simulation profile. Existing governance, capacity,
inventory/inspection, previews and logical-charge suites now visit storage;
delegation tools visit settings. `capabilities.mjs` checks the A1-required home
redirect for members, then explicitly reopens the operations alias after a grant.
The administration top-bar link now uses the existing compact icon/label pattern;
controls wrap on phones, fixing administrator-name overflow found by the new test.

Next by plan order: P1 staff records/basic directory, then P2 reviewed changes.
General health, analytics and settings content remain their cards.

## A2 audit explorer

Backend: `audit_catalog.py` is the single list of audit actions (group plus a plain sentence with `{actor}`,
`{target}`, `{unit}` and detail placeholders). `tests/test_audit_catalog.py` parses every `audit.record(...)`
and `AuditEvent(...)` call and fails when an `action=` literal, conditional or dynamic name (`auth.*_redeemed`,
`inventory_job.*`) has no entry; add the entry in the same change as the new action. `audit_explorer.py` builds
the filtered keyset query on `(created_at, id)` and shapes events; `api/audit.py` serves the list and the
streamed export (administrators only, `require_console("audit", admin_only=True)`). Migration 0028 adds indexes
on `(created_at, id)`, actor, target and scope; its downgrade only drops indexes. Tests: `test_audit_catalog.py`,
`test_audit_explorer.py` (filters, paging during inserts, formula escaping, cap, audited export, denials, no content).

Frontend: `features/audit/` (`AuditPage`, filters kept in the URL, `AuditTable`, `AuditDetail` drawer with the
sentence and before/after table, `ExportAudit`). The drawer opens from `?entry=` and only for entries on the
loaded page. Browser check: `e2e/audit.mjs` (with `e2e/audit-fixture.py`) at `/` and `/labadda-staging`: paging,
filters, drawer, export, retry, axe at 1400 and 390 px, member denial.


## A7 backups page and settings; AD-11 broadcasts

Backend: `backup_report.py` turns the D3 status file (`backup_status.read_status`, strict schema and 4 KiB limit,
reused not copied) into the page payload and the AD-03 word: missing, unreadable or future-dated is `unknown` with
guidance, never an error; failed backup or verification is `unavailable`; older than 26 h `degraded`; older than
50 h `stale`. Next run and restore rehearsal are `null` (the receipt does not carry them) and the page says "Not
recorded". `settings_report.py` lists an explicit set of non-secret `Settings` fields in groups with a plain
explanation; add a row there to expose a new setting, never iterate over `Settings`. Every row says "Changed by the
operator in the site configuration file." The first row is the software version (`build_info.py`).

Broadcasts replaced the single site notice. `broadcast.py` holds the rules (300 characters, one line, no control
characters, at most 20, `expected_revision`, active flag, optional window, `position` order, audited as
`site.broadcast_add/_edit/_move/_delete` without the text). Deleting is allowed: a broadcast is site configuration,
not user content. `api/admin_site.py` serves `/admin/backups/status`, `/admin/settings`, `/admin/broadcasts` (console
section `broadcast`, administrators only) and `/site/broadcasts` (any signed-in person, panel 401). Migration 0039
creates `site_broadcasts`, moves the old `site_banner` row into broadcast 1 and drops the old table; its downgrade
refuses unless the broadcasts fit one old notice. `labadda create-admin` on the very first account of a pilot
installation adds the pilot-testing warning (`seed_pilot_notice`, audited as `site.broadcast_seed`); test fixtures
start with none. Tests: `test_admin_site.py`, `test_broadcast.py`.

Frontend: `features/admin/BackupsPage.tsx`, `Settings.tsx` (groups `SettingsGroups.tsx`, then the delegation tools),
`BroadcastPage.tsx` (DataTable, ConfirmDialog) with `features/broadcast/BroadcastDialog.tsx`, `useAdminData.ts`.
`features/broadcast/BroadcastStrip.tsx` is the scrolling strip (WCAG 2.2.2: Pause/Play button, paused on hover and
focus, still list under reduced motion, one polite status region); `Shell.tsx` polls `/site/broadcasts` through
`useBroadcasts.ts` every minute and gives it a full-width row under the top bar. Help: `help/admin/backups-page.md`,
`broadcast.md`, `settings.md`. Browser checks: `e2e/console-backups.mjs` and `e2e/console-broadcast.mjs` at `/` and
`/labadda-staging`: both themes, axe at 1400 and 390 px, member denial.

## A4 system health and events

Backend: `backend/labadda/health/` has one module per AD-07 item (`application`, `database`, `file_storage`,
`connections`, `jobs`, `response_time`, `sign_in`, `backups`, `server`, `certificate`). Each has a pure
`evaluate(...)` over injected readings and a `check(ctx)` that reads, and returns `Result(status, value, unit,
detail, checked_at)`. `types.Context` holds the injectable readers (clock, `/proc` via `proc.Proc`, disk, socket
count, backlog, registry, heartbeat). Reading `/proc` fails as `ProcUnavailable` and becomes `unsupported`.
`catalog.py` lists the items with their help page and 24-hour chart series. `sampler.Sampler` measures all items
every `LABADDA_HEALTH_SAMPLE_SECONDS` (15) from `scheduler.run_periodic`, keeps the latest results in memory,
serves a result older than 60 s as `stale`, and calls `events.apply`. Thresholds are `health_thresholds.py`
(`LABADDA_HEALTH_*`, documented in `deploy/labadda.env.example`). `scheduler.run_forever` records a
`heartbeat` tick after each full pass and a failure for each failed job; `Hub.backlog()` feeds Live connections.

Rules chosen: unknown and unsupported never raise or resolve an event; only `healthy` resolves; a problem word
(`degraded`, `unavailable`, `stale`) keeps one live event per `<item>.<status>` (partial unique index) and a
change of word supersedes the older one; events are raised from the current reading, not only from changes, so
a hand-resolved event whose item still fails cannot hide it (resolve returns 409 `still_failing`). Acknowledging
changes only the event. An absent certificate report is `unsupported` (AD-07); an unreadable one is `unknown`.
The certificate file is `certificate-status.json` (`format`, `checked_at`, `expires_at`) in `LABADDA_STATUS_DIR`;
no operator tool writes it yet.

Migration 0030 `ops_events` (downgrade refuses while rows exist). API in `docs/API.md` (A4). Audit actions
`ops_event.acknowledge` and `ops_event.resolve` are in `audit_catalog.py`.

Test-only forcing: `LABADDA_TEST_HEALTH_FORCE=item=status,...` or the file `.test-health-force` in the asset
directory; both are honoured only when `environment` is `development` or `test`.

Frontend: `features/health/` (page, card, 24-hour chart, model) and `features/events/` (page, drawer, model),
sharing `features/admin/usePolledData.ts` (polling paused while the tab is hidden, last good data kept on a
failed poll, `useNow` for "checked N s ago"). The card word turns `Stale` in the browser after four intervals.
Help: `help/admin/{system-health,status-words,events}.md` and `help/troubleshooting/health-*.md`.

Checks: `tests/test_health_items.py` (every status per item), `test_health_events.py` (dedupe, recovery,
stale, forced, migration guard), `test_health_api.py` (access, denials, paging, acknowledge, no content),
vitest `features/health`, browser `e2e/console-health.mjs` at `/` and `/labadda-staging`.

## A5 usage analytics

Backend package `analytics/`: `periods.py` (7/30/90 days and 12 months as whole site-local days, plus the
previous period), `samples.py` (bounded reads of `metric_samples` — day buckets, then hours after the newest
day, then minutes after the newest hour, so nothing counts twice — and of `activity_days`), `summary.py`
(site totals, tiles, six charts), `units.py` and `protect.py` (small-group protection), `export.py` (CSV
rows of exactly the published figures), `cache.py` (60 s, 32 entries). `api/analytics.py` serves
`/admin/analytics/summary`, `/units` and `/export.csv` (`require_console("activity")`, 2 s statement bound,
authority rechecked after reading and before an export is delivered; `analytics.export` is audited).

Protection is decided on exact values and only the result leaves the server: a unit row is published when
at least 5 of its home people were active; while suppressed rows (that have people) hold fewer than 5 active
people together, the smallest published row is suppressed too, because site totals are exact and
"total minus published units" would otherwise reveal them; published people counts are rounded to the
nearest 5, so nested or adjacent periods cannot be subtracted down to one person; a unit counts only its own
home people, never its sub-units. People without an organisation home unit form one more protected row.
Item counts per unit are rounded too and have their own complementary rule (`published_items`): the
"Organisation units" total is exact, so hidden units' items (units with no home people included) must
total at least 5 and be spread over at least two hidden units. Site figures have a floor: people figures
below 5, chart buckets and weekdays with fewer than 5 active people, and item and upload totals in a period
with fewer than 5 active people are sent as `suppressed`. Projects and groups are reported only as "Projects"
and "Groups" item totals.

Accepted residual risks (privacy review, 2026-11-12):

- **Transfers.** Activity is grouped by each person's *current* home unit; there is no home-unit history in
  the people tables the card allows. An administrator who moves someone across a unit's 5-person threshold
  (or a rounding boundary) and compares the page before and after can learn about that person. Transfers are
  audited, which makes this visible. `test_home_units_are_read_as_they_are_now` pins the behaviour. A
  stricter fix needs a home-unit history (P2/P3 change records) and is left for that work.
- **Sliding windows.** Rounding to 5 is deterministic, so watching one unit day by day as a period slides
  can show when its count crosses a rounding boundary. It never shows which person. No activity row and no sample
in the period is `unknown`; a figure without its data is `unknown` with `value: null`. Upload size bands come
from the new `uploads.size_band` counter (no figures before this release).

Tests: `test_analytics.py` (unknown states, site time zone, roll-up cut-offs, tiles and comparison, cache,
denial matrix, audited export, no content for every period) and `test_analytics_units.py` (suppression,
complementary suppression, rounding, overlapping periods, parent and sibling differencing, no home unit,
chart top 10 + other, projects and groups never by name).

Frontend `features/activity/` (`ActivityPage` with the period in the URL, `ActivityTiles`, `ActivityCharts`,
`UnitActivity`, `ExportActivity`). Suppressed figures read "Fewer than 5" and are never charted. Help:
`help/admin/activity-page.md`. Browser check `e2e/console-activity.mjs` (with `e2e/activity-fixture.py`) at
`/` and `/labadda-staging`: tiles, every chart, suppressed and rounded unit rows, no project or group names,
table view, period in the URL, audited export, usage reader deep link, member refusal, axe at 1400/390 px.

## A6 overview

Backend `overview/`: `attention.py` (health, event and people entries, ordering), `tiles.py` (the six tiles and two
charts), `build.py` (assembly); `api/overview.py` serves `GET /admin/overview` (section `overview`, readers allowed, 2 s
bound, authority rechecked after reading). It reuses `api.health.current_items`, the Activity page's cached 7-day
summary (same cache key, so its floor is applied once), `backup_report` for the last-backup age, and the latest
`metric_samples` gauges. People figures below 5 (including signed-in now and each day of its trend) are `suppressed`.
An open event about an item that already has a health entry is not listed twice. Units without an active steward or
Head are the only people item until P5. Tests: `test_overview.py` (clean site, severity order, no double listing,
unknown/stale, suppression and agreement with the Activity page, access matrix, no content).

Frontend `features/overview/` (`OverviewPage`, `Attention`, `Tiles`, `Charts`, `model.ts`): the `/admin` index. It uses
the new `ui/StatTile` (label link, figure, status word, note, trend slot; gallery entry and test), `Sparkline`,
`LineChart`, `StatusPill`, `EmptyState` and `Card` only. It polls every 15 s through `usePolledData` (paused while the
tab is hidden), shows "Updated N s ago" and marks figures stale after four missed polls. Hidden figures read "Fewer
than 5" and missing ones "Not measured", never 0. Help: `help/admin/overview-page.md`. Browser check:
`e2e/console-overview.mjs` (with `e2e/overview-fixture.py`) at `/` and `/labadda-staging`: nothing-needs-attention, three
entries in severity order with working links, polling picks up and clears a problem, usage reader, member refusal, axe
at 1400/390 px. `e2e/admin-console.mjs` now expects the Overview page at the index.
