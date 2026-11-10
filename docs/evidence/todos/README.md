# C1 task validation

Synthetic validation completed on 2026-11-10. Final backend verification passed
424 tests including real isolated recovery and migration drift checks; frontend
verification passed31 tests, typecheck and production build. Independent review
found and verified corrections to backend expiry/lock ordering and frontend stale
selection/conflict recovery. Actual PostgreSQL blocking regressions are included.

`e2e/todos.mjs` passed60 checks at root and `/labadda-staging`, using five synthetic
users across sibling sections and their division. Checks include owner-only lists,
colleague/admin/parent-only denial, upward ancestor access, Unicode/date/checklists,
completion/reopening, lost list/task replies with exactly-once creation, revision
conflicts and deliberate draft replacement, late save after list switching,
post-create denied refresh, and delayed rename after a denied refresh. Desktop and
390px mobile axe/overflow checks passed; screenshots are generated in the supplied
output directory (default `/tmp/labadda-todos`). No manual accessibility/site/device
acceptance is implied.

Run on fresh `scripts/proxy-stack.sh start` fixtures. The browser script removes
Ben's Section A membership; reset before subsequent member-dependent flows. Keep
interception patterns stable while a response is paused: removing a single-use
GET interceptor during a paused PUT invalidated the original harness request.
The corrected regression releases paused responses before changing those rules.

Broader C2 coordination (assignments, comments, status/history, task sockets and
My Tasks) remains separate. Developer source map: [task guide](../../development/tasks.md).
