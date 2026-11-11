# Agent workflow

How a coding agent (or a person) takes one work package from the plan to a pushed, verified
change. Follow the steps in order. The protocol is deliberately mechanical so that a short
prompt such as "do the next work package" produces a complete, reviewable result.

## 1. The loop

| Step | Do | Output |
| --- | --- | --- |
| 1. Select | Open [the plan](../plan/README.md). Take the first package marked `in progress`, else the first marked `next`. Do not skip ahead; packages depend on earlier ones. | Package ID |
| 2. Claim | Set its status to `in progress` in the plan table and commit that one-line change. | Commit |
| 3. Read | The card, the contract IDs it lists, [standards.md](standards.md), the nearest `AGENTS.md`, the code and tests you will touch. | Notes |
| 4. Plan | Write the list of files to add or change, the tests to add, and the order of commits. Split into slices that each leave `verify.sh` green. | Short plan |
| 5. Contract | Update `docs/API.md` (and the spec, only if the card says so) before the code. | Doc diff |
| 6. Build | Backend with tests first, then frontend, then the browser check, then help and guides. | Code |
| 7. Verify | Run the card's acceptance checks and `scripts/verify.sh` (`--e2e` if a screen changed). Use the feature in a real browser against the fixture. | Results |
| 8. Self-review | Answer the seven questions in [standards.md §6](standards.md#6-self-review-before-you-commit). | Fixes |
| 9. Record | Set the package status and percentage in the plan; add a handoff entry to `ROADMAP.md`. | Doc diff |
| 10. Push | Commit and push to `main` as [AGENTS.md §6](../../AGENTS.md#6-git) describes. | Pushed SHA |

If a package is too large to finish in one session, finish a slice that is green, record exactly
what remains in the handoff entry, and leave the status `in progress`.

## 2. Sizing

- Aim for commits of 100–500 changed lines. A commit over 800 lines of hand-written code is a
  sign the slice should be split (mechanical reformat commits are the exception).
- One migration per commit. One new screen per commit.
- Never mix a mechanical change (formatting, renaming, moving) with a behaviour change.

## 3. Statuses used in the plan

`done` · `in progress` · `next` (ready to start, dependencies met) · `queued` (waiting for an
earlier package) · `owner` (needs the site owner or a real host; an agent prepares, the owner
executes) · `deferred` (outside v1.0).

## 4. Handoff entry template

Add a row at the top of the ledger table in `ROADMAP.md`. Keep it under 120 words. Link to
evidence instead of pasting output.

```markdown
| 2026-11-14 · P2 · done | Transfer preview/apply API and dialog. Tests: `test_people_transfer.py` (14), `e2e/people-transfer.mjs` (22 checks at / and prefix). `verify.sh --e2e` green. | Assumed a transfer keeps project and group memberships (PO-12). | Start P3. |
```

Columns: date · package · status | what changed and the evidence | assumptions, limits, open
questions for the owner | the exact next action.

When the ledger passes 15 rows, move the oldest rows to a file in `docs/history/` in the same
commit.

## 5. Evidence

- Evidence is the test or script that proves the behaviour, committed in the repository.
- Screenshots are optional. If a card asks for them, store them under
  `docs/evidence/<package>/` with a short `README.md`, fictional data only, PNG under 300 KB.
- Do not paste terminal transcripts into documents. Record the command, the totals and the SHA.

## 6. Ready-made prompts for the owner

These are complete. Paste one as the whole instruction to a coding agent.

**Continue the plan**

> Follow AGENTS.md. Do the next work package in docs/plan/README.md from start to finish,
> including tests, browser checks, help page, plan status and handoff entry. Push to main.
> Stop only for the reasons in AGENTS.md section 7.

**Do a specific package**

> Follow AGENTS.md. Do work package `<ID>` from docs/plan. Finish every acceptance check on the
> card. Push to main and report the checks you ran and their results.

**Review the last package** (use a different model or a fresh session from the one that built it)

> Follow REVIEW.md. Review the commits of work package `<ID>` against its card and the contract
> IDs it lists. Try the denied cases yourself. Report findings by severity with file and line.
> Do not change code.

**Fix review findings**

> Follow AGENTS.md. Fix the findings below for work package `<ID>`. For each one add a test that
> fails before the fix. Do not change anything else. Push to main.

**Report status**

> Read docs/plan/README.md and ROADMAP.md. Run scripts/verify.sh. Tell me, in plain language,
> what is finished, what is in progress, what is next, and whether the checks pass. Change nothing.

## 7. Working well as a less capable model

These habits matter more than cleverness.

- **Read before writing.** Open the neighbouring feature that is most similar and copy its
  shape. Most defects come from inventing a second way to do something that already exists.
- **Small steps, run often.** Run the one relevant test file after each function, not the whole
  suite at the end.
- **When a test fails, read the failure.** Find the cause. Do not change the assertion, add a
  retry, widen a timeout or catch the exception to make it pass.
- **Do not guess an API.** If you are unsure a function, column or endpoint exists, search for
  it. If it does not exist, the card will say to create it; otherwise stop and ask.
- **Do not widen the task.** A problem you notice outside the card goes into the handoff entry
  as a note. It does not go into the diff.
- **Prefer boring.** A plain loop, a plain table, a plain form. No metaprogramming, no generic
  framework, no configuration system for a single caller.
- **Say what you did not do.** An honest "not done: X, because Y" is worth more than a claim
  that later proves false.

## 8. Independent review

Authorization, people and organisation changes (track P), metrics that touch usage data
(A3, A5) and anything that changes sessions or delivery need a review by a different model or
person before the package is marked `done`. Record the reviewer, the SHA reviewed and the
outcome in the handoff entry. Other packages are self-reviewed with the checklist.
