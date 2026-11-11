# Admin console v1 — contract

Status: **normative for v1.0; not yet implemented** except where "Exists today" says so.
Delivered by track A of [the plan](plan/admin.md). Summarised in
[SPECIFICATIONS.md S10](../SPECIFICATIONS.md).

[ADMIN-CONSOLE.md](ADMIN-CONSOLE.md) (AC-01–AC-21) remains the long-term contract. This document
is the **v1.0 delivery profile**: the part of it that is built now, written concretely enough
to implement without further design. Where the two differ, this document governs v1.0 and the
"Deferred" table at the end says what waits.

**Purpose.** One place where an administrator with no systems background can see, at a glance
and live, whether LabAdda is healthy, how it is being used, what needs attention, and who
changed what — and can act on it safely. People and organisation screens are specified in
[PEOPLE-AND-ORG.md](PEOPLE-AND-ORG.md) and live inside this console.

## Exists today

A single `/admin` page with accounts, units, memberships, capacity proposals, partial storage
observations, inventory receipts and jobs, and usage-reader delegations; `/operations` for
delegated readers; `GET /admin/audit` (latest rows, no screen); `/healthz` and `/readyz`.
Source: `frontend/src/pages/Admin.tsx`, `Operations.tsx`, `backend/labadda/api/admin.py`,
`governance.py`, `usage.py`, `capabilities.py`, `inventory_jobs.py`.

## Rules for every console page

**AD-01. Access.** Site administrators see everything in the console. *Usage readers* (the
existing time-limited `usage.read` delegation) see Overview, Activity, System health, Storage,
Backups and Events read-only. Unit administrators (PO-24) see only People and Organisation for
their branch. Every endpoint checks this on the server on every call. Board-only sessions get
401. Nobody gets content access from the console.

**AD-02. Metadata only.** The console shows names of people and units, counts, sizes, rates,
durations, times, statuses and event codes. It never shows message or post text, note titles,
file names, board images, search terms or request bodies. Projects and collaborative groups
appear in analytics only as the totals "Projects" and "Groups", never by name.

**AD-03. Status words.** Every health item and tile uses exactly one of `healthy`, `degraded`,
`unavailable`, `stale`, `unknown`, `unsupported`, shown as icon + word. No samples is `unknown`,
not zero. A value older than its freshness promise is `stale`. Something this installation
cannot measure is `unsupported`. The overall state is the worst item state, ignoring `unsupported`.

**AD-04. Every number explains itself.** Unit, period covered, last-updated time, and a link to
the list or chart behind it. Layout, tiles, charts and refresh follow
[UX-09 and UX-10](development/ui-design-system.md).

**AD-05. Cheap to run.** Console pages read only the metrics, activity, event and audit tables
described here, plus a few bounded counts cached for 60 s with a 2 s statement timeout. They
never scan content tables on request and never take locks that could delay the whiteboard or
chat. Collection costs at most one small batched insert per minute.

## Pages

| Route | Shows | Actions |
| --- | --- | --- |
| `/admin` Overview | Overall state; attention list (health problems, open events, people attention items from PO-22, backup age); tiles: people active today, signed-in now, connected now, storage used, last backup, open events; 7-day activity and response-time charts | Open the item behind each entry |
| `/admin/people`, `/admin/org` | See PEOPLE-AND-ORG.md | See PEOPLE-AND-ORG.md |
| `/admin/activity` | Usage analytics (AD-08) | Choose period, compare with previous period, view as table, export CSV |
| `/admin/health` | Live system health (AD-07) and 24-hour charts | Open the help page for any item that is not healthy |
| `/admin/storage` | Existing storage, capacity, inventory and job views, moved here unchanged in behaviour | Existing actions |
| `/admin/backups` | Last backup time, age, size, verification result, destination alias, next scheduled run, last restore rehearsal (AD-10) | Open the backup and restore guides |
| `/admin/audit` | Searchable audit trail (AD-09) | Filter, open detail, export CSV |
| `/admin/events` | Operational events (AD-06) | Acknowledge with a note, resolve, open the guide |
| `/admin/settings` | Site name and time zone; site notice banner (AD-11); effective limits and timeouts read-only with a plain explanation and where each is changed; administrators and delegations | Edit banner; manage delegations |
| `/admin/help` | Administrator handbook and setup checklist ([HELP-CENTER.md](HELP-CENTER.md)) | — |

Every page is deep-linkable, keeps its filters in the URL, and has a help link.

## Data and collection

**AD-06. Operational events.** Table `ops_events`: `id, code, component, severity
(info|warning|error|critical), summary, detail (sanitised JSON), first_at, last_at, count,
state (open|acknowledged|resolved), acknowledged_by, acknowledged_at, note, resolved_at`.
Repeats of the same `code` + `component` while one is open increase `count` and `last_at`
instead of adding rows. Events are raised when a health item changes state, a scheduled job
fails, a scheduled people change needs review, sign-in failures spike, or disk or backup age
crosses a threshold. A health item that recovers resolves its event automatically; acknowledging
never turns a failing item green. Every event code has a page in the administrator help with:
what it means, what users notice, what to check, what to do, when to call the operator.

**AD-07. Health items.** Each is a small function returning `{status, value, unit, detail,
checked_at}`. Sampled every 15 s in the background and served from memory; the page polls.

| Item | Measured | Degraded / unavailable when |
| --- | --- | --- |
| Application | Version, uptime, database schema matches the release | Schema behind or ahead of the code |
| Database | Round-trip time, connections used of the maximum, database size | Slow (> 250 ms), > 80 % of connections, unreachable |
| File storage | Free space and free inodes on the asset volume, against the configured reserve | Below reserve + 20 %; below reserve |
| Live connections | Connected sockets, signed-in sessions seen in the last 5 minutes | Delivery queue backlog beyond its bound |
| Background jobs | Seconds since the scheduler last completed a tick; failed runs in the last hour | > 2 minutes; > 10 minutes |
| Response time | p50 and p95 of API requests over 5 minutes; error rate | p95 > 1 s; error rate > 2 % |
| Sign-in | Successful and failed sign-ins over 15 minutes | Failure rate spike above the configured threshold |
| Backups | Age and verification of the latest backup receipt (AD-10) | Older than 26 h; older than 50 h or failed verification |
| Server | Process memory, host load, host memory (from `/proc`) | Above configured thresholds; `unsupported` if unreadable |
| Certificate | Days until the site certificate expires, from the operator status file | < 30 days; < 7 days; `unsupported` if not provided |

Thresholds are settings with the defaults above, documented in `deploy/labadda.env.example`.

**AD-08. Metrics and analytics.**

*Storage.* Table `metric_samples (bucket_start, resolution, metric, dimension, value, samples)`
with a unique key on the first four columns. Resolutions and retention: `minute` 48 hours,
`hour` 35 days, `day` 2 years. The scheduler rolls minutes into hours and hours into days and
deletes expired rows; roll-up is idempotent. The metric set is fixed in code
(`backend/labadda/metrics/catalog.py`), at most 60 metrics and 40 dimension values per metric;
anything outside the catalogue is rejected.

*Collection.* Counters and latency histograms are kept in process memory by a small middleware
and by explicit calls at the commit point of each feature, then flushed once a minute. A lost
minute on restart is acceptable and shows as a gap. Retries of an idempotent operation count
once. Health probes, scheduler work and asset requests are not counted as user activity.

*Catalogue (v1).* `http.requests`, `http.errors`, `http.latency_p50/p95` by route group;
`auth.signin_ok`, `auth.signin_failed`; `sessions.active`, `sockets.connected` (gauges);
`posts.created`, `replies.created`, `chat.messages`, `board.operations`, `tasks.created`,
`tasks.completed`, `uploads.count`, `uploads.bytes`, `notifications.created` — each feature
counter with dimension = top-level unit kind (`org`, `project`, `group`) and, separately, by
organisation unit ID for `org` workspaces; `db.size_bytes`, `assets.bytes`, `disk.free_bytes`.

*People activity.* Table `activity_days (user_id, day)` with one row per person per site-local
day on which they made at least one authenticated request, written at most once per person per
day. It supports: people active per day, week and month; active people by home unit; people
who have not signed in for N days. Kept 2 years. It records no pages, actions or times.

*Activity page.* Period selector (7, 30, 90 days, 12 months) with comparison to the previous
period. Tiles: active people (day / week / month), share of all active accounts, peak
simultaneous connections, items created. Charts: active people per day; activity by feature
(stacked bars); activity by weekday and hour (heat grid, from hourly request counts); activity
by unit (bars, top 10 plus "other", with a table of all); storage growth; uploads by size band.
**Small-group protection:** any per-unit figure covering fewer than 5 people shows "fewer than
5" and is left out of charts; filters cannot be combined to isolate one person.

**AD-09. Audit explorer.** Filters: date range, actor, person, unit, action group (people,
access, organisation, authority, sign-in security, settings, exports), outcome, free text over
reason. Newest first, cursor pagination, stable order. A detail drawer shows before and after as
a readable sentence plus the structured values. Rows cannot be edited or removed from the
console. CSV export of the filtered set (up to 10 000 rows, formula-escaped) is itself audited.
Actions are named in plain words through one catalogue in code that maps each audit action to a
sentence; an action missing from the catalogue fails a test.

**AD-10. Backups page.** The web application does not run backups. The operator tooling
(`scripts/lifecycle.py`, timer from package D3) writes a small status file after each run into
the directory named by `LABADDA_STATUS_DIR`: time, result, size, verification, destination
alias, schema, release. The console reads and validates that file (strict schema, size limit,
no paths or secrets displayed). If the file is missing the page says backups are `unknown` and
links to the set-up guide — it never implies that backups exist.

**AD-11. Site notice banner.** An administrator can publish one short plain-text notice to all
signed-in users (for example planned maintenance), with a start and end time and a level
(info or warning). It is audited, escaped, limited to 280 characters and removed automatically.

**AD-12. Interfaces** (full shapes go in docs/API.md with each package):

```text
GET  /admin/overview
GET  /admin/health
GET  /admin/metrics/series?metric=&dimension=&from=&to=&resolution=
GET  /admin/analytics/summary?period=            GET /admin/analytics/units?period=
GET  /admin/audit?…filters…&cursor=              GET /admin/audit/export.csv?…
GET  /admin/events?state=&severity=&cursor=      POST /admin/events/{id}/acknowledge | /resolve
GET  /admin/backups/status
GET  /admin/settings                             PUT /admin/settings/banner
GET  /site/banner                                (any signed-in user)
```

## Acceptance

Tests T61–T66 in [TESTING.md](../TESTING.md) are release gates, including: no content field in
any console response; small-group protection; `unknown`/`stale` never rendered as healthy or
zero; console load does not slow a concurrent whiteboard rehearsal beyond the S4 targets.

## Deferred beyond v1.0

| Long-term requirement | Why it waits |
| --- | --- |
| AC-03 two-person approval; AC-04–AC-08 policy drafting, dry run, scheduling and activation | Needs quotas and retention (P5.3–P5.6), which are outside v1.0 |
| AC-06/AC-07 destructive plans; lifecycle and archive pages | No destructive lifecycle exists in v1.0 |
| AC-17–AC-19 web-triggered backup, restore and emergency pause | Operator tooling covers these; the console shows status only |
| AC-15 saved views, incident assignment; AC-11 capacity forecast with confidence bounds | After a real site has several months of samples |
