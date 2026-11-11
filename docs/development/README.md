# Developer task map

Use [repository rules](../../AGENTS.md) first, then [the workflow](agent-workflow.md) and
[engineering standards](standards.md). For screens, follow the [UI design system](ui-design-system.md).
Read one relevant feature guide, then its linked contract/tests; consult broader specifications
when changing a boundary. Run the affected checks and update the same guide, the
[plan](../plan/README.md) and the ledger with the code.

For the remaining v1.0 areas, work-package cards name the modules to create; add a guide here (one file per area, under 150 lines) when the first package of an
area lands: `people.md`, `admin-console.md`, `metrics.md`, `help-centre.md`.

| Task | Minimal source path | Contract / checks |
| --- | --- | --- |
| To-do lists, scope or retry behaviour | [Tasks guide](tasks.md) → backend/labadda/api/todos.py, task_history.py and frontend/src/pages/Todos.tsx | S8/CT-01–05, API C1, tests/test_todos.py, e2e/todos.mjs |
| Assignment / My Tasks | [Assignment guide](task-assignment.md) → api/task_assignment.py | CT-07, T44, test_task_assignment.py |
| Task discussions | [Comments guide](task-comments.md) → api/task_comments.py | CT-08, T45, test_task_comments.py |
| Conversation to task | [Conversion guide](task-conversion.md) → api/task_conversion.py, ConversationTask.tsx | CT-10, T47, test_task_conversion.py |
| Board/research-plan task context | [Board reference guide](task-board-references.md) → api/task_board_conversion.py, Board.tsx | CT-11, T48, test_task_board_conversion.py |
| Chat threads / colleague communication | [Chat guide](chat.md) → api/chat.py | CT-12, T49, test_chat_threads.py |
| Daily owner dashboard | [Dashboard guide](dashboard.md) → api/dashboard.py, pages/Dashboard.tsx | CT-14, T51, test_dashboard.py |
| Owner alert preferences | [Preferences guide](alert-preferences.md) → api/alert_preferences.py, notify.py | CT-15, T52, test_alert_preferences.py |
| Staff records / people directory | [People guide](people.md) → people.py, api/people.py, features/people/ | PO-01–03/20, test_people_*.py, test_staff_migration.py, e2e/people.mjs |
| Reviewed staff edits / preview and apply | [Change guide](people-changes.md) → changes/, api/changes.py | PO-04–12, test_change_plan.py, test_changes_edit.py; P2 in progress |
| Admin console routing / operational access | [Console guide](admin-console.md) → policy.py, deps.py, api/capabilities.py | AD-01–02, test_console.py, test_capabilities.py |
| Shared authorization | backend/labadda/policy.py, deps.py, identity_locks.py, memberships.py | SPECIFICATIONS S2; tests/test_policy.py; feature negative tests |
| Shared UI components, tokens, theme | [UI kit guide](ui-kit.md) → frontend/src/ui/ | UX-01–UX-14, T69, src/ui/*.test.tsx, e2e/ui-kit.mjs |
| Workspace/browser navigation, shell | frontend/src/App.tsx, features/shell/ (Shell, TopBar, RailNav, WorkspaceSwitcher), pages/WorkspaceView.tsx | e2e/flows.mjs; root and configured-prefix checks |
| Schema and recovery | backend/labadda/models.py, migrations/versions, recovery.py | tests/test_migrations.py and test_recovery_integration.py |
| Shared task update signals | [Update guide](task-updates.md) → task_events.py and task routers | CT-09, T46, test_task_events.py |
| Realtime delivery | backend/labadda/realtime.py, frontend/src/realtime.ts | tests/test_realtime.py; REVIEW.md; P4-QUALIFICATION.md |
| Multi-user regression qualification | [Simulation guide](simulation.md) → scripts/simulate.py, rehearsal.py, e2e | test_simulation.py, test_rehearsal_report.py; full root/prefix profile |
| Deployment / service / probes | [Operations guide](operations.md) → scripts/operations.py, release.py | test_operations.py, test_release.py; DEPLOYMENT.md, RECOVERY.md |
| Operational inventory jobs | backend/labadda/inventory_jobs.py, api/inventory_jobs.py | INVENTORY-JOBS.md; focused job/API tests |

All source/test paths above are relative to the repository root (backend test files
live in backend/tests). Do not run parallel pytest sessions against the same test
database: its fixtures recreate the schema. Browser proxy startup resets only its
disposable databases. Preserve development and research-demo data.
