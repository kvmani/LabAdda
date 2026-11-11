# LabAdda roadmap

Short on purpose. The detailed, ordered work and the completion percentages are in
[docs/plan/README.md](docs/plan/README.md). The full history of delivered stages, with evidence,
is in [docs/history/roadmap-to-2026-11-11.md](docs/history/roadmap-to-2026-11-11.md).

## Where we are (2026-11-11)

**About half way to v1.0.** The collaboration product is built and locally qualified; the work
that remains is mostly what makes it *manageable and pleasant*: the admin console, people and
organisation management, in-app help, a consistent design system, uniform code, and proof on a
real host.

| Phase | Scope | State |
| --- | --- | --- |
| P0 Design | Specification, permission model, test and review plans | Done |
| P1 Foundation | Sign-in, tree, memberships, policy, shell, root/prefix | Verified on synthetic data |
| P2 Noticeboard | Posts, replies, files, reminders, notifications, notes, groups | Verified on synthetic data |
| P3 Realtime | Whiteboard, snapshots, chat, presence, replay | Verified on synthetic data |
| P4 Touch and pilot qualification | Panel sessions, offline release, backup/restore, workload rehearsal | Software verified locally; real host, physical panel and manual review open (plan track D) |
| C1–C5 Collaboration | Tasks, assignment, comments, conversion, threads, chat files, My day, alert preferences | Verified locally; optional alerts deferred (C6) |
| P5.1 Measurement | Usage observations, capacity proposals, inventory, upload admission | Implemented, observation only |
| **v1.0 tracks Q, U, A, P, H, D** | Quality gates, design system, admin console, people and organisation, help, deployment | **Current work — see the plan** |
| P5.2–P5.7 Lifecycle | Quotas, retention, archives, re-import | Specified, deferred beyond v1.0 |
| P6 Expansion | Federation, direct messages, e-mail, multi-site | Deferred |

## Standing decisions

- 2026-11-09 — Collaboration (C1–C5) takes priority over lifecycle work (P5.2+).
- 2026-11-11 — Production readiness: deployment, upgrade, recovery automation and a multi-user
  regression harness; no new archive features.
- 2026-11-11 — v1.0 is defined in the plan. Admin console v1, people and organisation
  management and in-app help are in scope; the long-term admin contract (AC-01–AC-21) is
  delivered in part, as listed in [ADMIN-CONSOLE-V1.md](docs/ADMIN-CONSOLE-V1.md).
- Real-site acceptance, physical-device tests and pilot activation belong to the site owner and
  are never closed by local evidence.

- 2026-11-11 — Owner accepted all U2 decisions: link-list rail, narrower full-name
  rail, light theme until U4 and My profile in P8.

## Open decisions for the owner

1. Confirm the v1.0 scope and package order in the plan.
2. The three defaults at the end of [PEOPLE-AND-ORG.md](docs/PEOPLE-AND-ORG.md).
3. Whether C6 (assignment and deadline alerts) joins v1.0.

## Handoff ledger

Newest first. Template and rules: [agent-workflow.md §4](docs/development/agent-workflow.md#4-handoff-entry-template).
When this table passes 15 rows, move the oldest to `docs/history/`.

| Date · package · status | What changed and evidence | Assumptions, limits, questions | Next action |
| --- | --- | --- | --- |
| 2026-11-11 · A1 · in progress | Shared console policy/dependency and metadata-only navigation endpoint; existing admin/storage gates migrated without new rights.18 focused console/delegation checks passed after review corrections; full verify passed (604 backend,84 frontend, clean drift/lint/build). | U2 decisions accepted by owner. No new roles/content access; web split follows. | Complete lazy console navigation and move existing tools; run acceptance suites. |
| 2026-11-11 · U2 · done | New shell in `frontend/src/features/shell/` on ui/ tokens: sticky top bar (live status, notifications with count, Help, Administration, account menu with Alert preferences and Sign out), full-height rail of links, three layouts (≥1200, 900–1199 narrower rail, <900 switcher with icon-only controls). `/help` placeholder until H1. Old shell CSS removed; global styles now load before component styles. Evidence: full simulation 36/36 stages, 465 browser checks across 11 suites (same as baseline), both 30-client TLS workloads with zero missing, lost, duplicate or cross-workspace deliveries; accessibility audit 38/38 at 1366, 1024 (new) and 390 px with no findings; `verify.sh --e2e` green (594 backend, 84 unit, flows 69/69, ui-kit 18/18). | Selector changes, same meaning: 26 readiness waits from the "Sign out" button to the account menu button; flows sign-out now opens the account menu; "● Live" and `.conn-online` to the "Live" status text. Decisions for the owner on the U2 card: rail kept as links (not TreeView), app forced light until U4, My profile added in P8. | A1, U3, A3, H1, P8 and U4 are available; next by plan order is A1. |
| 2026-11-11 · U1 · done | `frontend/src/ui/`: tokens (light/dark, contrast-checked), theme choice applied before first paint, 31 components (buttons, fields, display, overlays with focus trap, tabs, data table, tree view) and a dev-only gallery at `/_ui`. Guide: `docs/development/ui-kit.md`. Evidence: 83 unit tests (49 new: 42 component, 7 theme/token); `e2e/ui-kit.mjs` 18/18 (axe zero violations in both themes at 1400 and 390 px, dialog focus/Escape); flows 69/69; accessibility audit 34/34, no findings; production bundle unchanged (gallery excluded). Screenshots reviewed: fixed right-aligned columns and doubled field spacing. | Legacy screens stay on a fixed light palette until U2/U4. `e2e/accessibility.mjs` had a stale `#chat-input` selector since `847e9e1` and never completed; updated to the current composer form. It is not in any automated profile. | U2 (shell) and U3 (charts) are next; A3 also next. |
| 2026-11-11 · Q2 · done | ESLint (type-checked, hooks, jsx-a11y) and Prettier gate in `verify.sh`; no `any` in `frontend/src`; `noUncheckedIndexedAccess` and `noImplicitOverride` on. Typed API responses and socket events; shared error helpers; `invalidate()` for request counters. Found and fixed: two unhandled rejections (board reload, admin members), an "[object Object]" history label, and Q2's own regression in Todos revocation, caught by `e2e/task-updates.mjs` (fix `eb53c93`). Evidence: lint clean; 34 unit tests (31 before); flows 69/69 before and after; flows, todos, assignment, comments, task-updates, conversion, board-reference, dashboard, alert-preferences suites all pass; chat-threads 6/8 vs pre-Q2 6/8 and chat-attachments 3/3 vs 3/3 in interleaved runs. | Known flaky waits in chat-threads and chat-attachments predate Q2; recorded on the Q3 card. A full simulation run did not reach the TLS workloads because it stops at the first flaky failure; Q2 changed no backend code. React Compiler lint rules deferred to Q3. | U1 (design system) and A3 (metrics) are next. |
| 2026-11-11 · Q1 · done | Ruff 0.17.4 format and lint gate in `verify.sh` for backend, scripts and e2e. Mechanical format and safe-fix commits, then hand fixes by rule family. String splits were checked by AST equality; generated nginx config is byte-identical. Every exemption states its reason. Evidence: 594 backend tests passed, 0 skipped, before and after (recovery tests on); `alembic check` clean; frontend 31 tests and build green. | Ruff's unsafe C416 fix broke `policy.py` (`dict(Result)`), was caught by the suite and fixed: review unsafe fixes. Pushed migrations were formatted (no AST change) but are otherwise frozen and exempt from E501. The ruff wheel is now in the lock file and so in offline release wheelhouses, like pytest. | Q2; Q3 enables the four deferred function-size rules. |
| 2026-11-11 · Q5 · done | Rewrote agent guidance (AGENTS.md, nested guides, standards, workflow, design system); added v1.0 plan with 34 packages; added contracts for people and organisation (PO), admin console v1 (AD) and help (HP); S9–S13 and T53–T71; archived the old roadmap ledger; added `scripts/check_docs.py` to `verify.sh` with tests. Docs check green. | Documentation and one checker only; no application behaviour changed. Backend and browser suites were not re-run in this session (no database in the authoring environment). Percentages are estimates. | Start Q1 and Q2. |
| 2026-11-11 · Operations stage 5 · verified locally | Full regression (465 browser checks, two 30-client TLS workloads), 573 backend checks, offline release build/verify/install. [Evidence](docs/evidence/operations/README.md). | Built on Debian 13; real systemd, site TLS, off-host transfer and timed recovery not exercised. | Plan package D1. |
