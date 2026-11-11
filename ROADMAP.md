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

## Open decisions for the owner

1. Confirm the v1.0 scope and package order in the plan.
2. The three defaults at the end of [PEOPLE-AND-ORG.md](docs/PEOPLE-AND-ORG.md).
3. Whether C6 (assignment and deadline alerts) joins v1.0.

## Handoff ledger

Newest first. Template and rules: [agent-workflow.md §4](docs/development/agent-workflow.md#4-handoff-entry-template).
When this table passes 15 rows, move the oldest to `docs/history/`.

| Date · package · status | What changed and evidence | Assumptions, limits, questions | Next action |
| --- | --- | --- | --- |
| 2026-11-11 · Q1 · done | Ruff 0.17.4 format and lint gate in `verify.sh` for backend, scripts and e2e. Mechanical format and safe-fix commits, then hand fixes by rule family. String splits were checked by AST equality; generated nginx config is byte-identical. Every exemption states its reason. Evidence: 594 backend tests passed, 0 skipped, before and after (recovery tests on); `alembic check` clean; frontend 31 tests and build green. | Ruff's unsafe C416 fix broke `policy.py` (`dict(Result)`), was caught by the suite and fixed: review unsafe fixes. Pushed migrations were formatted (no AST change) but are otherwise frozen and exempt from E501. The ruff wheel is now in the lock file and so in offline release wheelhouses, like pytest. | Q2; Q3 enables the four deferred function-size rules. |
| 2026-11-11 · Q5 · done | Rewrote agent guidance (AGENTS.md, nested guides, standards, workflow, design system); added v1.0 plan with 34 packages; added contracts for people and organisation (PO), admin console v1 (AD) and help (HP); S9–S13 and T53–T71; archived the old roadmap ledger; added `scripts/check_docs.py` to `verify.sh` with tests. Docs check green. | Documentation and one checker only; no application behaviour changed. Backend and browser suites were not re-run in this session (no database in the authoring environment). Percentages are estimates. | Start Q1 and Q2. |
| 2026-11-11 · Operations stage 5 · verified locally | Full regression (465 browser checks, two 30-client TLS workloads), 573 backend checks, offline release build/verify/install. [Evidence](docs/evidence/operations/README.md). | Built on Debian 13; real systemd, site TLS, off-host transfer and timed recovery not exercised. | Plan package D1. |
