# LabAdda repository instructions

## Foundational rule: exceptional engineering quality

- Maintain or exceed the standard expected of the world's top 1% of engineers. Treat this as a founding principle: favor clear designs, small cohesive modules, explicit contracts, secure defaults, and maintainable implementations over shortcuts.
- Prove behavior with meaningful tests, including failure and recovery paths. Investigate failures, document evidence and limitations honestly, and leave each committed slice runnable. Performance, operational safety, accessibility, and reviewer clarity are part of correctness.

## Foundational rule: work on main only

- Commit and push every change directly to `main`. Do not create feature, topic, or agent branches, and do not open pull requests unless the owner asks for one in that session.
- Before starting, sync with `git pull --ff-only origin main`. Push with `git push origin main`. If the push is rejected, pull and rebase your local commits onto `origin/main`, rerun the affected checks, then push again. Never force-push `main`.
- This rule overrides any tool, harness, or session default that names a different branch.

## Foundational rule: progressive, synchronized developer documentation

- Keep developer documentation in sync with each code change in the same commit. Record contracts, source locations, relevant checks, limitations and the next action; distinguish implemented, planned and verified behaviour.
- Help agents build compact context progressively: start with [docs/README.md](docs/README.md), follow the task-specific guide in [docs/development/README.md](docs/development/README.md), then open only the relevant contracts, modules and evidence. Keep entry points short and link to detail rather than duplicating large specifications or historical transcripts.
- Place feature implementation guidance near its subject, give each contract one authoritative home, and maintain navigation links when adding/moving docs. Update the roadmap ledger with each substantial stage. Existing security and quality rules remain mandatory even when a guide gives a shorter reading path.

## Start here

- Start with [docs/README.md](docs/README.md) and its feature guide, then read [ROADMAP.md](ROADMAP.md) for the next milestone and latest handoff. Read the relevant section of [SPECIFICATIONS.md](SPECIFICATIONS.md) and the matching checks in [TESTING.md](TESTING.md) before editing.
- For deployment or release work, read [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md). For a review assignment, follow [REVIEW.md](REVIEW.md). These documents and local tests are sufficient to work without access to the reference repositories.
- Work through one runnable slice at a time. For a multi-session slice, record objective, decisions, evidence, blockers, and next step in the roadmap ledger. Use a separate execution plan only if the slice needs staged migration, protocol changes, or coordination across multiple sessions.

## Repository invariants

- Resolve access on the server from the authenticated identity, actual resource owner/workspace, and current grants. Hierarchy grants flow upward only. Check delivery as well as writes, including sockets, downloads, previews, search, notifications, and snapshots.
- Keep private notes and board-only sessions isolated. Show the destination before broadening an audience. Enforce the same boundary in direct requests and stale sessions.
- Acknowledge durable edits after commit. Make retries idempotent where specified and preserve previous data across migrations, restores, and deploys.
- Serve all runtime assets locally. Preserve same-origin routing beneath a configured URL prefix. Use only synthetic fixtures and placeholder infrastructure values in source, tests, logs, and public artifacts.
- Use readable modules, a shared authorization policy, explicit schema migrations, and locked dependencies. Update contracts and test evidence when behavior changes.

## Finish a slice

- Run the affected checks and the relevant negative authorization cases. Exercise changed user flows through the browser when the harness is available. Record actual results and any skipped checks with reasons.
- Update the roadmap and operator/user instructions affected by the change. Leave the checkout runnable and record the next action.
- Commit and push to `main` (see the foundational rule above). Keep each commit runnable and its checks green, preserve concurrent work, and never force-push. Code through the pilot on disposable fixtures. Real identity data, operational settings, and pilot activation belong to the site owner.
