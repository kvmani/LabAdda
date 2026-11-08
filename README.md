# LabAdda

LabAdda is a browser-based collaboration workspace for research teams on an air-gapped office intranet. Sign in once, switch between your team and its parent units, and use each workspace's noticeboard, live whiteboard, and group chat. My Notes gives each user a separate personal space.

Users can also create **collaborative groups** with chosen colleagues from any unit. A group has the same noticeboard, whiteboard and chat as a section, without hierarchy.

The repository holds a runnable application (FastAPI + PostgreSQL backend, React + Vite frontend) with fictional fixture data. See [ROADMAP.md](ROADMAP.md) for what is complete and what comes next.

| Document | Use it for |
| --- | --- |
| [AGENTS.md](AGENTS.md) | Repository rules and agent starting point |
| [SPECIFICATIONS.md](SPECIFICATIONS.md) | Product scope, access rules, workflows, and service contracts |
| [ROADMAP.md](ROADMAP.md) | Implementation order, milestone exits, and handoff ledger |
| [TESTING.md](TESTING.md) | Test matrix and release evidence |
| [REVIEW.md](REVIEW.md) | Independent review procedure and release decisions |
| [Intranet deployment design](docs/DEPLOYMENT.md) | Runtime, offline release, staging, recovery, and site decisions |
| [API contract](docs/API.md) | Endpoints, error codes, idempotency and socket messages |
| [Design sources](docs/REFERENCES.md) | Patterns taken from the four reference projects and agent guidance |

The product display name and GitHub repository slug are both **LabAdda**. Use lowercase `labadda` for machine identifiers (package, CLI, environment variables, cookies, databases).

## Run locally (development, fictional data)

Prerequisites: Ubuntu 24.04, Python 3.12, PostgreSQL 16, Node 22 (build-time only), nginx (only for proxy tests).

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
scripts/verify.sh          # pytest on PostgreSQL, alembic drift check, typecheck, unit tests, production build
scripts/verify.sh --e2e    # also starts root + /labadda-staging instances behind nginx and runs browser flows
```

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
