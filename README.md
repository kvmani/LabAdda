# LabAdda

Developer/agent entry point: [documentation map](docs/README.md).

LabAdda is a browser-based collaboration workspace for research teams on an air-gapped office intranet. Sign in once, switch between your team and its parent units, and use each workspace's noticeboard, live whiteboard, and group chat. My Notes gives each user a separate personal space.

Users can also create **collaborative groups** with chosen colleagues from any unit. A group has the same noticeboard, whiteboard and chat as a section, without hierarchy.

Chat supports **threads and validated file attachments**, including private-group conversations. Personal/shared to-do lists include assignment, workflow and discussion; posts/chat and board context can become reviewed tasks. **My day** combines current-access work, private deadlines, mentions and unread conversations; **Alert preferences** controls your in-app categories. See [chat usage](docs/usage/chat.md), [tasks](docs/usage/tasks.md) and [My day](docs/usage/dashboard.md).

Each readable workspace has a **Storage** tab with shared file and logical-content observations. It covers that workspace's content only; personal notes and parent/child totals are separate. These partial counters do not activate workspace quotas or retention.

Administrators can save observation-only site capacity proposals and preview asset-budget/reserve scenarios. Previews show incomplete measurements and upper bounds; saving or previewing does not activate limits. See [API and current boundaries](docs/API.md#p51-site-capacity-proposals-and-previews).

The repository holds a runnable application (FastAPI + PostgreSQL backend, React + Vite frontend) with fictional fixture data. See [the delivery plan](docs/plan/README.md) for what is complete (about half of v1.0) and what comes next.

| Document | Use it for |
| --- | --- |
| [AGENTS.md](AGENTS.md) | Repository rules and agent starting point |
| [SPECIFICATIONS.md](SPECIFICATIONS.md) | Product scope, access rules, workflows, and service contracts |
| [Delivery plan](docs/plan/README.md) | v1.0 scope, completion percentages, ordered work packages |
| [ROADMAP.md](ROADMAP.md) | Phase overview, standing decisions, and handoff ledger |
| [Engineering standards](docs/development/standards.md) | How code is written here; recipes; self-review |
| [Agent workflow](docs/development/agent-workflow.md) | Step-by-step protocol and ready-made prompts for coding agents |
| [UI design system](docs/development/ui-design-system.md) | Tokens, components, layouts, charts, wording |
| [People and organisation](docs/PEOPLE-AND-ORG.md) | Staff records, transfers to retirement, org chart, import (v1.0 contract) |
| [Admin console v1](docs/ADMIN-CONSOLE-V1.md) | Overview, health, analytics, audit, events (v1.0 contract) |
| [In-app help](docs/HELP-CENTER.md) | Help centre, setup checklist, sync checks (v1.0 contract) |
| [TESTING.md](TESTING.md) | Test matrix and release evidence |
| [REVIEW.md](REVIEW.md) | Independent review procedure and release decisions |
| [Intranet deployment design](docs/DEPLOYMENT.md) | Runtime, offline release, staging, recovery, and site decisions |
| [API contract](docs/API.md) | Endpoints, error codes, idempotency and socket messages |
| [Data lifecycle requirements](docs/DATA-LIFECYCLE.md) | Future quotas, retention, user archives and safe re-import |
| [Portable archive format](docs/ARCHIVE-FORMAT.md) | Future offline-readable packages, validation and round trips |
| [Admin console long-term requirements](docs/ADMIN-CONSOLE.md) | Policy controls, approvals and lifecycle safety beyond v1.0 |
| [Design sources](docs/REFERENCES.md) | Patterns taken from the four reference projects and agent guidance |

The product display name and GitHub repository slug are both **LabAdda**. Use lowercase `labadda` for machine identifiers (package, CLI, environment variables, cookies, databases).

## Run locally (development, fictional data)

Prerequisites: Ubuntu 24.04, Python 3.12, PostgreSQL 16, Node 22 (build-time only), system IANA tzdata, nginx (only for proxy tests).

```bash
# 1. Disposable databases (development only)
sudo -u postgres psql -c "create role labadda login password 'labadda-dev' createdb"
sudo -u postgres createdb -O labadda labadda_dev
sudo -u postgres createdb -O labadda labadda_test

# 2. Install locked dependencies
python3.12 -m venv .venv
.venv/bin/pip install -r backend/requirements.lock
.venv/bin/pip install --no-deps -e backend
(cd frontend && npm ci && npm run build)

# 3. Migrate, load the fictional fixture, start on loopback
cd backend
export LABADDA_ENV=development
../.venv/bin/labadda migrate
../.venv/bin/labadda seed --reset        # erases and reloads fixture data; refused outside development/test
../.venv/bin/labadda serve --port 8000  # open http://127.0.0.1:8000/
```

Fixture accounts all use the development-only password `fixture-pass-123` (override with `LABADDA_FIXTURE_PASSWORD`):

| User | Role in the fictional tree |
| --- | --- |
| `admin` | Org administrator with no content grant |
| `asha` | Steward, Thin Films Section (Section A) |
| `ben` | Member, Section A; steward of the *Microscopy Reading Club* group |
| `chen` | Member, Catalysis Section (Section B); member of the reading club group |
| `dana` | Steward, Surface Science Division; steward of Project Aurora |
| `eli` | Project Aurora guest only |
| `fay` | Disabled account in Section A |

For a prefixed instance, set `LABADDA_BASE_PATH=/labadda-staging` and a distinct `LABADDA_COOKIE_NAME`. All settings are listed in [deploy/labadda.env.example](deploy/labadda.env.example).

**Touch panel.** Open `<base>/panel` in a separate browser profile or kiosk window on the panel. On a desktop, open a whiteboard, choose **📺 Open on touch panel**, and type the code on the panel. Timing is set by `LABADDA_PANEL_IDLE_SECONDS` (300), `LABADDA_PANEL_ABSOLUTE_MINUTES` (60) and `LABADDA_PANEL_PAIRING_SECONDS` (120).

For frontend development with hot reload, run `npm run dev` in `frontend/`. It proxies `/api` and `/ws` to port 8000.

## Test

```bash
scripts/verify.sh          # docs check, pytest on PostgreSQL, alembic drift check, typecheck, unit tests, production build
scripts/verify.sh --e2e    # also starts root + /labadda-staging instances behind nginx and runs browser flows
```

Full S4 workload rehearsal (30 signed-in clients, 8 drawers, two sibling workspaces). Every client holds a live socket; the run fails on any lost, duplicated, undelivered or cross-workspace event. Use the TLS mode of the local stack to exercise https/wss, Secure cookies and the proxy path. Raise the activation rate limit only for the disposable stack, or let the harness wait it out:

```bash
LABADDA_PROXY_TLS=1 LABADDA_LOGIN_ATTEMPTS_PER_WINDOW=100 scripts/proxy-stack.sh start
cd scripts && ../.venv/bin/python rehearsal.py --origin https://127.0.0.1:8080 \
  --cafile ../var/proxy-stack/tls/ca.crt --clients 30 --drawers 8 --seconds 900 --enforce-targets
cd .. && scripts/proxy-stack.sh stop
```

Accessibility audit (axe-core WCAG 2.1 A/AA rules, keyboard skip link and focus visibility, phone-width overflow, touch panel), on a fresh HTTP stack: `node e2e/accessibility.mjs http://127.0.0.1:8080 /tmp/labadda-accessibility`.

Drawing soak (8 drawers). It measures committed-update latency and checks for lost or duplicated edits. Run it against a freshly started test stack, because it creates accounts and activation is rate limited:

```bash
scripts/proxy-stack.sh start
.venv/bin/python scripts/soak.py --drawers 8 --seconds 120
scripts/proxy-stack.sh stop
```

`LABADDA_TEST_DATABASE_URL` selects the disposable test database. The default is `labadda_test` on localhost. The e2e stack uses `labadda_e2e_root` and `labadda_e2e_prefix`. Create both like `labadda_test`. CI (`.github/workflows/ci.yml`) runs `scripts/verify.sh` on the same locked dependencies.

## Operator commands

`labadda migrate` applies migrations. `labadda create-admin <username>` prints a one-time activation code. `labadda reminders` processes due reminders once. The server also runs reminders, provisional-upload cleanup and board compaction every 30 s (`LABADDA_BOARD_COMPACT_THRESHOLD`, `LABADDA_BOARD_KEEP_REVISIONS`). The service template and proxy template are in [deploy/](deploy/).

## Offline release tooling

See [the release procedure](docs/RELEASES.md) for connected builds, verified offline installation, runtime preflight, atomic activation and the conservative schema rollback rule. [P4 step 2 evidence](docs/RELEASE-EVIDENCE.md) records the clean Ubuntu 24.04 offline installation and current limitations. Backup and isolated restore are implemented; see [the recovery procedure](docs/RECOVERY.md). Site pilot qualification remains open.

## P5 foundations in progress

After migrations, users can open **My storage usage**. Administrators can save **non-enforcing** site proposals, inspect partial usage and configure time-limited operational readers with password confirmation. Authorized readers use `/operations`; they receive no administration or private-content access. The trusted operator can run `labadda inspect-storage` for bounded, non-destructive original-file checks. See [implemented status and limits](docs/P5-PROGRESS.md). Complete metering, archive export/import, policy activation and retention are still future work; do not enable destructive jobs based on these partial observations.
