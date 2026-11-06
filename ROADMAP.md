# LabAdd roadmap and handoff

## Current checkpoint

**P0 design baseline. Next action is P1.** The repository has design documents only. Each phase below is a runnable increment. Complete a phase's tests and record evidence before starting dependent work. Site-specific questions can remain open while implementing with disposable defaults.

| Phase | Deliverables | Exit evidence |
| --- | --- | --- |
| P0 · Design | Specification, permission model, implementation roadmap, testing, review, and air-gap design | Cross-check links, scope, terms, and public-repo sanitization |
| P1 · Foundation | FastAPI and React scaffold, PostgreSQL migrations, fictional fixture command, sign-in and administration, policy module, workspace navigation and protected routes, root/prefix config, liveness/readiness. Include a stable local start/reset procedure for a disposable database. | A browser session switches from home to the division, fails to open the sibling, and sees a coherent empty state. Run auth matrix, migrations on PostgreSQL, and both proxy paths. |
| P2 · Noticeboard | Feed, composer and audience, replies, pins, official posts, validated attachments, scoped search, upcoming reminders, in-app notifications, owner-only My Notes | Browser flow creates a post with an attachment and due time, sees it after reload, and proves exclusion from sibling and personal scopes. Scheduler retry and asset cleanup tests pass. |
| P3 · Realtime | Persistent board, concurrent drawing, text/stickies, images, replay/dedupe, conflicts, presence, own undo and restore, immutable snapshot publishing, persistent workspace chat | Multiple browser sessions draw and chat, disconnect/reconnect, and converge. Test stale epochs, revocation during live traffic, restart recovery, and broader sharing of a fixed snapshot. |
| P4 · Touch and pilot qualification | Board-only session flow, large touch tools, lock/end, actual touch test; performance rehearsal, clean offline install and upgrade, operator docs, backup and restore, independent review | All blocking checks pass on a representative staging VM. Site owner records acceptance of identity, retention, display, and operational policy before real use. |
| P5 · Expansion | Measure usage and capacity, validate delegated administration and identity federation as needed, consider richer search and notification integrations | Separate agreed rollout plan with capacity and access review. |

## P1 starting instructions

1. Create backend, frontend, test, and deployment-template directories. Choose and lock compatible dependency versions, with a deterministic setup on Ubuntu 24.04 and Python 3.12. Document install, migrate, seed, start, and test commands in the README as soon as they exist.
2. Implement configuration and migrations for users, sessions, the workspace tree, and direct memberships. Seed an active administrator with no content grant, two users in Section A, a user in Section B, a division steward, a project guest, and a disabled account. Use a repeatable fixture recipe for development only.
3. Implement the policy matrix before adding content endpoints. Add tests for upward visibility, independent project membership, sibling isolation, admin separation, transfer, and protected routes. Use actual PostgreSQL for migration and concurrency checks.
4. Connect the shell to the real sign-in, workspace list, and selection endpoints. Label placeholders for unfinished features and add the first end-to-end test through the proxy. Provide one local verification entry point and a CI check that uses the same commands and synthetic fixtures.
5. Update this ledger with commands, observed output, unresolved issues, and the first P2 action. Deliver code and test evidence in a reviewable branch unless the owner specifies a different branch.

## Handoff ledger

Add an entry at the end of each meaningful tranche. Mark status as planned, active, blocked, or verified. Record failed and skipped checks and the reason. Prefer paths, test identifiers, and commit or CI links to long transcripts. Keep decisions and the immediate next action easy to find.

| Phase and status | Work and evidence | Decisions or open items | Next action |
| --- | --- | --- | --- |
| P0 · Design baseline | Product, authorization, runtime, test, and review documents | Display name LabAdd; repository LabAdda. Desktop workspace layout and canvas-first touch. Site identity and retention still open. | Start P1 on a disposable database. |
