# LabAdda repository instructions

## Start here

- Read [ROADMAP.md](ROADMAP.md) for the next milestone and latest handoff. Read the relevant section of [SPECIFICATIONS.md](SPECIFICATIONS.md) and the matching checks in [TESTING.md](TESTING.md) before editing.
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
- Use the branch requested by the owner. With no branch instruction, prepare a reviewable branch against main. Preserve concurrent work and never force-push. Code through the pilot on disposable fixtures. Real identity data, operational settings, and pilot activation belong to the site owner.
