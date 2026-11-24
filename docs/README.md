# Documentation map

Read this map first; follow the relevant path rather than loading every document.

**New here? A fifteen-minute path.** (1) The [repository README](../README.md) to run a checkout
with fictional data. (2) The [rules in AGENTS.md](../AGENTS.md), sections 2 and 4: what is never
broken and what "done" means. (3) The [delivery plan](plan/README.md) status table: what exists
and what is next. (4) The [developer task map](development/README.md) for where a feature's code
and tests live. (5) The latest [review](development/review-2026-11-24.md) for known gaps. Skip
`history/` and `evidence/` unless a card sends you there.

| Need | Start here | Follow only as needed |
| --- | --- | --- |
| **What to build next; how complete the project is** | [v1.0 delivery plan](plan/README.md) | Track cards: [quality](plan/quality.md), [interface](plan/ui.md), [admin console](plan/admin.md), [people and organisation](plan/people.md), [help](plan/help.md), [deployment](plan/deployment.md) |
| How to work (protocol, handoff, prompts) | [Agent workflow](development/agent-workflow.md) | [Engineering standards](development/standards.md), [UI design system](development/ui-design-system.md) |
| People and organisation management | [Contract PO-01–25](PEOPLE-AND-ORG.md) | [Track P cards](plan/people.md), T53–T60 |
| Admin console, health, analytics | [v1.0 profile AD-01–12](ADMIN-CONSOLE-V1.md) | [Long-term contract](ADMIN-CONSOLE.md), [track A cards](plan/admin.md), T61–T66 |
| In-app help | [Contract HP-01–11](HELP-CENTER.md) | [Track H cards and page list](plan/help.md), T67–T68 |
| Phase overview and latest handoff | [Roadmap](../ROADMAP.md) | [Developer task map](development/README.md); [archived ledger](history/roadmap-to-2026-11-11.md) only for old evidence |
| Review collaboration screenshots | [Five-person capture guide](evidence/collaboration-review/README.md) | Research scenario, reproducible gallery and current feature limits |
| Chat, threads and private sharing | [Chat help page](../frontend/src/help/using/chat-and-threads.md) | [Implementation guide](development/chat.md), C4 thread/file checks |
| My day overview | [My day help page](../frontend/src/help/using/my-day.md) | [Developer guide](development/dashboard.md), active work, private deadlines, mentions and unread source bounds |
| Use to-do lists | [To-do lists help page](../frontend/src/help/using/tasks.md) | Personal vs workspace scope, saving and conflict recovery |
| Research-plan board references | [Board reference guide](development/task-board-references.md) | Recorded context, live board links and source permissions |
| Conversation to task | [Conversion guide](development/task-conversion.md) | Reviewed copies, destination audience and protected sources |
| To-do lists / collaboration | [Task implementation guide](development/tasks.md) | S8 in [specifications](../SPECIFICATIONS.md), C1 in [API](API.md), T37–T42 in [testing](../TESTING.md) |
| Start and verify a checkout | [Repository README](../README.md) | [Testing](../TESTING.md), scripts/verify.sh |
| Multi-user regression system | [Simulation guide](development/simulation.md) | Dedicated disposable runner, CI, root/prefix screenshots and TLS workloads |
| **Which setup: dedicated VM, beside project_management_software, Windows; install/upgrade from the release zip** | [Deployment setups](deployment/README.md) | [PM facts and limits](deployment/pm-coexistence.md), [PM's nginx file](deployment/pm-reference/apex_pm.active.conf) |
| Run a site: install, check, back up, upgrade | [Operator quickstart](OPERATOR-QUICKSTART.md) | [Deployment](DEPLOYMENT.md); `sudo labadda-admin` lists every routine command ([setups guide](deployment/README.md)) |
| Feature trends and response times | [Insights help page](../frontend/src/help/admin/insights-page.md) | [Admin console guide](development/admin-console.md#insights-a8), A8 in [API](API.md) |
| Deployment and recovery | [Deployment](DEPLOYMENT.md) | [Recovery](RECOVERY.md), [commissioning](COMMISSIONING.md), [release evidence](RELEASE-EVIDENCE.md) |
| Authorization/security review | [Repository rules](../AGENTS.md), [review plan](../REVIEW.md) | Relevant feature contracts and negative tests |
| Existing usage/accounting/jobs | [P5 implementation status](P5-PROGRESS.md) | [Inventory jobs](INVENTORY-JOBS.md), API and focused tests |
| Future archives/policies | S5–S7 in [specifications](../SPECIFICATIONS.md) | DATA-LIFECYCLE.md, ARCHIVE-FORMAT.md, ADMIN-CONSOLE.md |

Current priority: the [delivery plan](plan/README.md) — the remaining module splits (Q4) and the
owner's site gates (track D: a real Ubuntu host, office devices and acceptance). Archive, quota
and retention work (P5.2+) is deferred beyond v1.0.

Specifications describe required behaviour; plan cards say what to build next; feature guides
describe implementation; the roadmap ledger records delivered evidence. Files under `history/`
and `evidence/` are snapshots, not the current product status.
