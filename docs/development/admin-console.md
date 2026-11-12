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


## A7 backups page, settings and site notice

Backend: `backup_report.py` turns the D3 status file (`backup_status.read_status`, strict schema and 4 KiB limit,
reused not copied) into the page payload and the AD-03 word: missing, unreadable or future-dated is `unknown` with
guidance, never an error; failed backup or verification is `unavailable`; older than 26 h `degraded`; older than
50 h `stale`. Next run and restore rehearsal are `null` (the receipt does not carry them) and the page says "Not
recorded". `settings_report.py` lists an explicit set of non-secret `Settings` fields in groups with a plain
explanation; add a row there to expose a new setting, never iterate over `Settings`. Every row says "Changed by the
operator in the site configuration file." `banner.py` holds the notice rules (280 characters, one line, no control
characters, `expected_revision`, audited as `site.banner_set` / `site.banner_clear` without the text);
`api/admin_site.py` serves `/admin/backups/status` (backups console section, readers allowed), `/admin/settings`
and `PUT /admin/settings/banner` (administrators only) and `/site/banner` (any signed-in person, panel 401).
Migration 0029 creates the single-row `site_banner`; its downgrade refuses while a notice exists. Tests:
`test_admin_site.py`.

Frontend: `features/admin/BackupsPage.tsx`, `Settings.tsx` (site notice editor `NoticeEditor.tsx`, groups
`SettingsGroups.tsx`, then the existing delegation tools), `useAdminData.ts`. `ui/Banner.tsx` (test, gallery entry)
renders the notice as text; `Shell.tsx` polls `/site/banner` through `useSiteBanner.ts` every minute and gives it a
full-width row under the top bar. Help: `help/admin/backups-page.md`, `site-notice.md`, `settings.md`. Browser check:
`e2e/console-backups.mjs` at `/` and `/labadda-staging`: unknown backup, fresh and stale receipts, settings without
paths or secrets, notice publish/appear/remove, member denial, axe at 1400 and 390 px.
