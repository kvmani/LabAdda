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

## Web delivery (next A1 slice)

Lazy-load `features/admin/AdminLayout.tsx`; move accounts/units/memberships to basic
People/Organisation, storage tools to `/admin/storage`, delegations to settings.
Future sections render honest placeholders. Recheck server-provided sections on
navigation; preserve `/operations` as a storage redirect. Add root/prefix browser
checks and move existing admin-suite browser visits without changing their meaning.
