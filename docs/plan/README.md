# LabAdda v1.0 delivery plan

This is the single source of truth for **what is done, what is next, and how much is left**.
Agents: take the first package marked `in progress`, else the first marked `next`, and follow
[the workflow](../development/agent-workflow.md). Update this file in the same commit as the work.

## What "v1.0" means

A LabAdda that one site can install on its intranet, that ordinary staff can run without a
system administrator, and that people enjoy using:

1. **Collaboration** — noticeboard, whiteboard, chat, tasks, My day, notes, groups (built).
2. **A modern, consistent interface** on a shared design system, light and dark.
3. **An admin console** with a live overview, system health, usage analytics, audit and events.
4. **People and organisation management** that handles joining, transfer, promotion, change of
   authority, leave, retirement and reorganisation graphically, with preview and audit.
5. **Help inside the app** for members, stewards, administrators and the server operator.
6. **Deployment that a careful non-expert can follow**, with verified backup and restore.
7. **Clean, uniform, linted, tested code** that future agents can extend from short prompts.

Outside v1.0 (kept specified, not scheduled): storage quotas and enforcement, retention and
purge, portable archives and re-import (P5.2–P5.7), identity federation, direct messages
outside groups, e-mail delivery, multi-site federation (P6).

## Status at a glance

Last updated: 2026-11-11 (after Q1, Q2, U1, U2, A1 and P1). Percentages are judged against the v1.0 definition above, weighted by
remaining effort, and are estimates — the package table below is the precise record.

| Area | Weight | Done | Remaining in short |
| --- | --- | --- | --- |
| Collaboration features (P1–P3, C1–C5) | 30 % | 90 % | Optional task alerts; site and device acceptance |
| Deployment, upgrade, backup, recovery tooling | 15 % | 75 % | Rehearsal on a real Ubuntu host, scheduled backups with status, operator quickstart, release 1.0 |
| Admin console, health and analytics | 20 % | 20 % | Metrics, health, activity, overview, audit, events, backups and general settings |
| People and organisation management | 12 % | 30 % | Change protocol, transfers to retirement, positions, org chart, import, unit administrators |
| Interface quality and design system | 10 % | 60 % | Charts (U3), moving existing screens onto the kit and enabling the dark theme (U4) |
| In-app help and onboarding | 6 % | 0 % | Framework, all content, setup checklist, sync check |
| Code uniformity and quality gates | 7 % | 70 % | Readable rewrite of compressed modules and the deferred rules (Q3), module splits (Q4) |
| **Overall toward v1.0** | 100 % | **≈ 57 %** | |

The delivered foundation includes 26 migrations, about 100 API endpoints and 724 backend
tests. The collaboration profile passed 465 root/prefix browser checks in U2; A1 adds 50
console checks and validates nine existing admin/tool suites. P1 adds 52 staff browser
checks, 94 frontend unit tests total, and two updated console lookup assertions. Thirty-client TLS workload
rehearsals and offline release, backup, restore and commissioning are verified locally.

## Order of work

Do packages in this order. A package may start only when everything it depends on is `done`.
Track D needs a real host and the site owner, so it runs alongside the others when available.

| # | ID | Package | Depends on | Status | Card |
| --- | --- | --- | --- | --- | --- |
| 1 | Q5 | Documentation gate (`check_docs.py`) and agent guidance | — | done | [quality](quality.md#q5--documentation-gate) |
| 2 | Q1 | Python formatter and linter gate | — | done | [quality](quality.md#q1--python-formatter-and-linter-gate) |
| 3 | Q2 | Frontend linter, formatter and strict types | — | done | [quality](quality.md#q2--frontend-linter-formatter-and-strict-types) |
| 4 | U1 | Design tokens and core components | Q2 | done | [ui](ui.md#u1--design-tokens-and-core-components) |
| 5 | U2 | Application shell refresh | U1 | done | [ui](ui.md#u2--application-shell-refresh) |
| 6 | A1 | Admin console shell and navigation | U2 | done | [admin](admin.md#a1--admin-console-shell-and-navigation) |
| 7 | P1 | Staff record, people list and profile | A1, Q1 | done | [people](people.md#p1--staff-record-people-list-and-profile) |
| 8 | P2 | Change protocol; add, edit, transfer | P1 | in progress | [people](people.md#p2--change-protocol-add-edit-transfer) |
| 9 | P3 | Positions, authority, leave, retirement, suspension | P2 | queued | [people](people.md#p3--positions-authority-leave-retirement-suspension) |
| 10 | A2 | Audit explorer | A1 | done | [admin](admin.md#a2--audit-explorer) |
| 11 | U3 | Charts kit | U1 | done | [ui](ui.md#u3--charts-kit) |
| 12 | A3 | Metrics foundation | Q1 | done | [admin](admin.md#a3--metrics-foundation) |
| 13 | A4 | System health and operational events | A1, A3, U3 | in progress | [admin](admin.md#a4--system-health-and-operational-events) |
| 14 | A5 | Usage analytics | A3, U3, P1 | in progress | [admin](admin.md#a5--usage-analytics) |
| 15 | A6 | Overview dashboard | A4, A5, P3 | queued | [admin](admin.md#a6--overview-dashboard) |
| 16 | P4 | Organisation chart and unit changes | P2 | queued | [people](people.md#p4--organisation-chart-and-unit-changes) |
| 17 | P5 | Scheduled changes and attention list | P3, P4 | queued | [people](people.md#p5--scheduled-changes-and-attention-list) |
| 18 | H1 | Help centre framework and sync check | U2 | done | [help](help.md#h1--help-centre-framework-and-sync-check) |
| 19 | H2 | Help for members and stewards | H1 | done | [help](help.md#h2--help-for-members-and-stewards) |
| 20 | H3 | Administrator handbook and setup checklist | H1, P5, A6 | queued | [help](help.md#h3--administrator-handbook-and-setup-checklist) |
| 21 | P6 | Staff list import and bulk changes | P3 | queued | [people](people.md#p6--staff-list-import-and-bulk-changes) |
| 22 | D3 | Scheduled backups with status file | — | done | [deployment](deployment.md#d3--scheduled-backups-with-status-file) |
| 23 | A7 | Backups page, settings and site notice | A1, D3 | done | [admin](admin.md#a7--backups-page-settings-and-site-notice) |
| 24 | P7 | Unit administrators | P4 | queued | [people](people.md#p7--unit-administrators) |
| 25 | P8 | My profile and sessions | U2 | done | [people](people.md#p8--my-profile-and-sessions) |
| 26 | U4 | Move existing screens onto the design system | U2 | in progress | [ui](ui.md#u4--move-existing-screens-onto-the-design-system) |
| 27 | Q3 | Readable rewrite of compressed modules | Q1, Q2 | queued | [quality](quality.md#q3--readable-rewrite-of-compressed-modules) |
| 28 | Q4 | Split oversized modules | Q3 | queued | [quality](quality.md#q4--split-oversized-modules) |
| 29 | H4 | Operator handbook, first-use welcome, what's new | H1, D2 | in progress | [help](help.md#h4--operator-handbook-first-use-welcome-whats-new) |
| 30 | D2 | Operator quickstart and `labadda doctor` | — | done | [deployment](deployment.md#d2--operator-quickstart-and-labadda-doctor) |
| 31 | D1 | Rehearsal on a disposable Ubuntu 24.04 host | — | owner | [deployment](deployment.md#d1--rehearsal-on-a-disposable-ubuntu-2404-host) |
| 32 | D4 | Site acceptance | D1, all above | owner | [deployment](deployment.md#d4--site-acceptance) |
| 33 | D5 | Release 1.0 | D4 | queued | [deployment](deployment.md#d5--release-10) |
| 34 | C6 | Assignment and deadline alerts (optional) | — | deferred | [below](#c6--assignment-and-deadline-alerts) |

## How to read a card

Each card has the same parts. **Goal** — the outcome in one sentence. **Contract** — the
requirement IDs to read. **Build** — what to create, with file locations. **Acceptance** — checks
you must run and see pass. **Not in this package** — things to leave alone. Sizes: S ≈ one
session, M ≈ two to three, L ≈ four or more; split M and L into green commits.

If a card and a contract disagree, stop and report it ([AGENTS.md §7](../../AGENTS.md)).

## C6 · Assignment and deadline alerts

Deferred, optional, size M. In-app alerts when a shared task is assigned to you and the day
before a task you own or are assigned is due, controlled by the existing alert preferences
(CT-15), with current-grant checks at creation and opening exactly as for mentions. Needs a
short contract (CT-16) agreed with the owner before work starts.

## Changing this plan

Only the owner adds, removes or reorders packages. An agent that finds a missing prerequisite
records it in the handoff entry and stops; it does not invent a package.
