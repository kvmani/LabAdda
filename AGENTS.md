# LabAdda repository instructions

LabAdda is a browser-based collaboration workspace (noticeboard, live whiteboard, chat, tasks,
personal notes) for research teams on an **air-gapped office intranet**. One Ubuntu VM, one
PostgreSQL database, a FastAPI backend and a React frontend. The people who run it day to day
are ordinary staff, not system administrators: every routine management job must be possible,
explained and safe **inside the web app**.

This file is the operating manual for every coding agent and human contributor. Follow it
exactly. When a rule here and your own preference disagree, the rule wins. When two documents
disagree, the order of authority is: this file → `SPECIFICATIONS.md` and the contract documents
it links → the work-package card → feature guides. Code that disagrees with a contract is a bug;
report it in your handoff instead of quietly changing the contract.

## 1. How to start any session

1. Sync: `git pull --ff-only origin main`.
2. If the owner gave you a specific task, do that task. Otherwise open
   [docs/plan/README.md](docs/plan/README.md), take the **first work package whose status is
   `next` or `in progress`**, and do only that package.
3. Read, in this order and nothing more: the work-package card → the contract sections it names →
   [docs/development/standards.md](docs/development/standards.md) → the nearest
   `backend/AGENTS.md` or `frontend/AGENTS.md` → the code you will edit and its tests.
4. Before writing code, write down (in your working notes or reply) the files you will touch,
   the tests you will add, and the acceptance checks from the card. If you cannot list them,
   you have not read enough.
5. Follow [docs/development/agent-workflow.md](docs/development/agent-workflow.md).

Do not read `docs/history/` or `docs/evidence/` unless a card sends you there. They are records
of finished work, not instructions.

## 2. Rules that are never broken

**Access and privacy**

- Decide access on the server from the signed-in identity, the resource's real owner or
  workspace, and the grants that exist *now*. Never trust an ID, role or scope sent by the client.
- Hierarchy grants flow upward only: a member of a section can read its division; a member of a
  division cannot read its sections. Projects and groups are flat and private.
- **Administrators never get content access from being administrators.** Admin, analytics,
  health, audit and people-management screens show names, counts, sizes, times and statuses —
  never message text, note titles, file names, board images or search terms.
- Check delivery as well as writes: sockets, downloads, previews, search, counts, notifications,
  exports and dashboards. Re-check grants just before returning protected data.
- Out-of-scope resources return the uniform 404. Signed-out requests return 401. A visible but
  not-permitted action returns 403. Never leak existence through counts, errors or suggestions.
- Personal notes, personal task lists and board-only panel sessions stay isolated from every
  other feature, including all new admin and analytics features.

**Data safety**

- Acknowledge a durable edit only after the database commit. Make retries idempotent where the
  contract says so. Never overwrite a concurrent edit silently: use the expected revision.
- Every schema change is an Alembic migration with a tested upgrade, and a downgrade that refuses
  to run when it would destroy data. Never edit a migration that has been pushed.
- Identity, membership, hierarchy and authority changes are written to the audit trail in the
  same transaction, with actor, target, before/after and reason.
- Nothing destroys user content in v1.0. Deactivate, archive and hide; do not delete.

**Air gap and secrets**

- No runtime request leaves the server: no CDN, web font, telemetry, external image or API.
  Every asset is bundled. Sole exception (owner-approved): feedback e-mail to the operator-named intranet relay.
  New dependencies: locked, free licence, card allows it, every pinned version >= 30 days old (`check_dependency_age.py`).
- Only fictional fixture data (source, tests, logs, screenshots, documents): Indian personal names
  and national-research-laboratory units, groups and projects, e.g. "Surface Engineering Division",
  "Project Tejas" (docs/development/fixture-names.md). Never commit real names, hosts or secrets.

**Honesty**

- Never claim a check passed unless you ran it and saw it pass. Record skipped checks with the
  reason. "Unknown", "stale" and "not measured" are shown as such, never as zero or healthy.
- Never weaken, skip, delete or loosen a test to make it pass. If a test is wrong, say why in
  the commit message and fix the test to match the contract.

## 3. Code quality bar

The full rules and worked recipes are in
[docs/development/standards.md](docs/development/standards.md). The short version:

- Make the smallest change that fully delivers the card. No drive-by refactors, no speculative
  options, no unused code, no commented-out code, no `TODO` without a work-package ID.
- Copy the pattern of the nearest existing feature before inventing a new one. Reuse
  `policy.py`, `deps.py`, `errors.py`, `audit.py`, `memberships.py` and the `frontend/src/ui`
  components instead of writing parallel versions.
- One module, one job. Split a file before it passes 400 lines; keep functions under 60 lines
  and lines under 110 characters.
- Typed everywhere: Pydantic models for every request body, typed TypeScript for every response.
  No new `any`, no `# type: ignore`, no `eslint-disable` without a one-line reason.
- Comments explain *why* a constraint exists. Do not narrate what the code does, and do not
  describe the change history in code.
- Every user-visible state is designed: loading, empty, error, forbidden, offline, saving,
  saved, conflict. Every control works with keyboard and screen reader.
- User-facing words are plain English for office staff. No jargon, IDs or stack traces on screen.

## 4. Definition of done

A work package (or any change) is done only when every line below is true:

- [ ] The card's acceptance checks pass, and you ran them.
- [ ] New behaviour has backend tests including the denied cases (sibling member, parent-only
      member, administrator without a grant, deactivated user, board-only session) that apply.
- [ ] Changed screens have a browser check in `e2e/` at both the root and the prefixed instance.
- [ ] `scripts/verify.sh` passes (run `scripts/verify.sh --e2e` when a screen changed).
- [ ] `docs/API.md` lists every new or changed endpoint, error code and socket message.
- [ ] The in-app help page for the feature is added or updated in the same commit (once the
      help centre exists — see [docs/HELP-CENTER.md](docs/HELP-CENTER.md)).
- [ ] The feature guide in `docs/development/` and the status in `docs/plan/README.md` are updated.
- [ ] A handoff entry is added to `ROADMAP.md` using the template in the workflow guide.
- [ ] The checkout runs: migrate, seed, serve, sign in, use the feature.

## 5. Commands

```bash
scripts/verify.sh                 # docs, Ruff, backend tests, drift, ESLint/Prettier, types, unit tests, build
scripts/verify.sh --e2e           # the above plus browser flows through nginx at / and /labadda-staging
python3 scripts/check_docs.py     # links, size limits and plan consistency only (seconds)
cd backend && ../.venv/bin/python -m pytest tests/test_<area>.py -q   # one area while iterating
```

Setup, fixture accounts and the local stack are in [README.md](README.md). Never run two pytest
sessions against the same test database: the fixtures recreate the schema.

## 6. Git

- Commit and push every change directly to `main`. Do not create feature, topic or agent
  branches and do not open pull requests unless the owner asks for one in that session.
- Push with `git push origin main`. If rejected, `git pull --rebase origin main`, rerun the
  affected checks, push again. Never force-push `main`.
- One work package may be several commits. Each commit must leave `scripts/verify.sh` green.
- Commit subject: imperative, under 72 characters, starts with the work-package ID when there is
  one, for example `P2: preview and apply staff transfers`. The body says what changed and
  which checks were run.

## 7. When to stop and ask the owner

Stop, leave the checkout green, and write the question in your handoff when:

- the card conflicts with a rule in section 2, or two contracts conflict;
- the change needs a new runtime dependency, a new service or process, or a change to the
  authorization model that the card does not name;
- a migration cannot be made lossless;
- you would have to touch real identity data, site settings, or anything outside this repository;
- the same check has failed three times for a reason you cannot explain.

Otherwise make the safest reasonable assumption, record it in the handoff, and continue.

## 8. Map

| Need | Document |
| --- | --- |
| What to build next, and how complete the project is | [docs/plan/README.md](docs/plan/README.md) |
| Step-by-step working protocol, handoff template, ready-made prompts | [docs/development/agent-workflow.md](docs/development/agent-workflow.md) |
| Coding standards and recipes | [docs/development/standards.md](docs/development/standards.md) |
| Look and feel, components, charts | [docs/development/ui-design-system.md](docs/development/ui-design-system.md) |
| Product contracts | [SPECIFICATIONS.md](SPECIFICATIONS.md) and the documents it links |
| Where the code for a feature lives | [docs/development/README.md](docs/development/README.md) |
| Acceptance tests | [TESTING.md](TESTING.md) |
| Independent review procedure | [REVIEW.md](REVIEW.md) |
| Deployment, recovery, commissioning | [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) |
