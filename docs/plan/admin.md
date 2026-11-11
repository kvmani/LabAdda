# Track A — admin console, health and analytics

Contract: [ADMIN-CONSOLE-V1.md](../ADMIN-CONSOLE-V1.md) (AD-01–AD-12). Layout and charts:
[ui-design-system.md](../development/ui-design-system.md) UX-09, UX-10.
Rule for the whole track: **no console response may contain content** (AD-02). Every package
adds a test that fetches its endpoints after seeding a recognisable post, chat message, note
title and file name, and asserts none of those strings appear in any response body.

### A1 · Admin console shell and navigation

Size M. Depends on U2.

**Goal.** `/admin` becomes a console with its own navigation and one page per area; existing
admin functions move in without behaviour change.

**Build.** `frontend/src/features/admin/AdminLayout.tsx` with the navigation in UX-03 and nested
routes for every page in the AD pages table; pages not yet built render an honest "Not available
yet" `EmptyState` (no fake data). Move existing blocks: accounts/units/memberships → temporary
"People (basic)" and "Organisation (basic)" pages; `Governance`, `StorageInventory`,
`InventoryJobs`, `DatabaseStorage`, `CapacityForecast`, `LogicalCharges` → `/admin/storage`;
`UsageReaders` → `/admin/settings`. Lazy-load the console as its own chunk. Backend: add
`deps.require_console(section)` implementing AD-01 for administrators and usage readers, and
use it on the existing admin and usage endpoints without widening anyone's access.

**Acceptance.** Existing admin, governance, capacity, inventory and usage-reader browser suites
pass at the new routes. `/admin/*` as a member → redirected home; as a usage reader → only the
read-only sections appear and other sections return 403 from the API; panel session → 401.

**Not in this package.** New data, new screens' content.

### A2 · Audit explorer

Size M. Depends on A1.

**Goal.** Administrators can search, read and export the audit trail (AD-09).

**Build.** Backend `api/audit.py`: filtered, cursor-paginated `GET /admin/audit`; streaming
`GET /admin/audit/export.csv` (formula-escaped, 10 000-row cap, audited as `audit.export`).
Index migration for `(created_at, id)`, actor and target. `audit_catalog.py`: one entry per
action → group, sentence template; a test enumerates every `audit.record(action=...)` literal
in the code and fails if one is missing from the catalogue. Frontend: filter bar, `DataTable`,
detail `Drawer` with the sentence and before/after values, export button.

**Acceptance.** Filters combine correctly; pagination is stable while rows are inserted; export
escapes `=`, `+`, `-`, `@`; non-administrators get 403; catalogue test passes.

### A3 · Metrics foundation

Size L. Depends on Q1. **Needs independent review** (touches every request).

**Goal.** A bounded, cheap metrics store and collector (AD-08) that later pages read.

**Build.** Package `backend/labadda/metrics/`: `catalog.py` (the fixed metric list with unit,
kind counter|gauge|histogram, allowed dimensions), `registry.py` (thread-safe in-memory
counters and fixed-bucket latency histograms; unknown metric raises), `middleware.py` (request
count, error count and latency by route group — derive the group from the route template, never
the raw path), `flush.py` (one batched upsert per minute from the scheduler tick), `rollup.py`
(minute→hour→day, retention deletes, idempotent), `gauges.py` (sessions, sockets, database
size, asset bytes, disk free). Migration: `metric_samples`, `activity_days`. Record
`activity_days` once per person per site-local day from `deps._load_actor` using an in-memory
"seen today" set to avoid a write per request. Add explicit `metrics.count("posts.created",
dimension=…)` calls at the commit point of each feature listed in the catalogue. API:
`GET /admin/metrics/series`. Settings for retention and flush interval.

**Acceptance.** Unit tests: registry concurrency, histogram percentiles, flush idempotency after
a crash between insert and reset, roll-up correctness across a day boundary in the site time
zone, retention. A retried idempotent post counts once. Health probes and static assets are not
counted. Cardinality guard rejects an unknown dimension. Load check: the S4 rehearsal
(`scripts/rehearsal.py`, 30 clients) stays within its targets with metrics on; record p95
before and after. No content strings in any metrics row (track rule).

**Not in this package.** Any screen.

### A4 · System health and operational events

Size L. Depends on A1, A3, U3.

**Goal.** A live health page and an events list with guidance (AD-03, AD-06, AD-07).

**Build.** `backend/labadda/health/`: one module per item in the AD-07 table, each returning
the common result shape; a sampler run from the scheduler every 15 s keeping the latest results
in memory; state changes raise or resolve `ops_events` (migration). Reading host figures from
`/proc` returns `unsupported` on failure, never an exception. Backup and certificate items read
the operator status file (schema in AD-10) and report `unknown` when absent. API:
`GET /admin/health`, `GET /admin/events`, acknowledge and resolve. Frontend: Health page — an
overall banner, a card per item with `StatusPill`, value, "checked 8 s ago", 24-hour chart, and
"What to do" link; Events page — filters, list, detail drawer, acknowledge with note.
Polling per UX-10.

**Acceptance.** Each item is unit-tested for every status it can return using injected readings
(database down, disk under reserve, scheduler stalled, missing status file, stale sample).
A recovered item resolves its event; an acknowledged failing item stays failing. Browser suite
forces a degraded state through a test-only setting and sees it within one poll, with the
guidance link. Usage reader can read, cannot acknowledge.

### A5 · Usage analytics

Size M. Depends on A3, U3, P1. **Needs independent review** (privacy).

**Goal.** The Activity page in AD-08, with small-group protection.

**Build.** `api/analytics.py`: `GET /admin/analytics/summary` and `/units` computed only from
`metric_samples`, `activity_days` and people/unit tables; results cached 60 s. Suppression
applied on the server (never send a figure the client must hide), including when two periods or
filters could be subtracted to reveal one person. Frontend page with period selector, tiles,
the six charts, table toggles and CSV export (audited).

**Acceptance.** Tests: suppression for units under 5 people; differencing attack (two overlapping
filters) cannot reveal a single person's activity; projects and groups appear only as totals;
periods are computed in the site time zone; empty installation shows `unknown`, not zeros.

### A6 · Overview dashboard

Size M. Depends on A4, A5, P3.

**Goal.** `/admin` opens on an overview that answers "is everything all right, and what needs
me?" (AD pages table, UX-10).

**Build.** `GET /admin/overview` assembling: overall state, attention list (health items not
healthy, open events by severity, people attention items, backup state), six tiles with
sparklines, two 7-day charts. Each entry carries the route that fixes it. Frontend page built
only from `ui/` components.

**Acceptance.** With a clean fixture the page says plainly that nothing needs attention. Seeding
a stale backup, a unit without a steward and an open event shows three attention entries in
severity order, each linking to the right screen. Loads in one request under 300 ms on the fixture.

### A7 · Backups page, settings and site notice

Size M. Depends on A1, D3.

**Goal.** AD-10 and AD-11, plus the read-only settings page.

**Build.** `GET /admin/backups/status` with strict validation of the status file. Settings page:
effective non-secret settings grouped and explained in plain words, each with "changed by the
operator in the site configuration file" or an edit control where the console owns it.
Site banner: migration, `PUT /admin/settings/banner`, `GET /site/banner`, a `Banner` in the shell.

**Acceptance.** Malformed, oversized or missing status file → `unknown` with guidance, never a
500. No path, hostname or secret value appears on the settings page (test asserts on a seeded
secret-like value). Banner shows to all users between start and end, is escaped, and is audited.
