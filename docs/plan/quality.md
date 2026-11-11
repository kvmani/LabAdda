# Track Q — code uniformity and quality gates

Goal of the track: every file reads the same way, and a machine refuses anything that does not.
See [standards.md](../development/standards.md) for the rules these gates enforce.

### Q5 · Documentation gate

**Status: done (2026-11-11).** `scripts/check_docs.py` checks every relative Markdown link and
anchor, the size limit of `AGENTS.md`, and that every package in the plan table has a card and
a valid status. It runs first in `scripts/verify.sh` and is covered by
`backend/tests/test_check_docs.py`.

### Q1 · Python formatter and linter gate

Size M. Depends on nothing.

**Goal.** All Python in `backend/` and `scripts/` is formatted by Ruff and passes a fixed lint
rule set, enforced by `scripts/verify.sh` and CI.

**Build.**

1. Add `ruff==<current stable>` to the `test` extra in `backend/pyproject.toml` and regenerate
   `backend/requirements.lock`. Add this configuration to `backend/pyproject.toml` and point
   `scripts/` at it with `ruff --config backend/pyproject.toml`:

   ```toml
   [tool.ruff]
   line-length = 110
   target-version = "py312"

   [tool.ruff.lint]
   select = ["E", "F", "W", "I", "B", "UP", "SIM", "C4", "PIE", "RET", "S", "BLE", "N", "PL", "RUF"]
   ignore = ["PLR0913", "PLR2004", "S101"]

   [tool.ruff.lint.per-file-ignores]
   "tests/*" = ["S105", "S106", "PLR0915"]
   "migrations/*" = ["N999"]
   ```

2. **Commit 1 — mechanical only:** run `ruff format backend scripts` and commit the result
   with the subject `Q1: format Python with Ruff (no behaviour change)`. Touch nothing by hand
   in this commit. Run the full backend tests before pushing.
3. **Commit 2 — safe automatic fixes:** `ruff check --fix` (no `--unsafe-fixes`), tests, commit.
4. **Commits 3+ — remaining findings by rule family**, one family per commit, fixed by hand.
   `BLE001` (blind except): catch the specific exception, or keep `Exception` only at a
   documented top-level boundary with a `# noqa: BLE001 — <reason>`. Do not change behaviour.
5. Add to `scripts/verify.sh`, before pytest: `ruff format --check` and `ruff check` for
   `backend` and `scripts`. Add the same to nothing else — CI already calls `verify.sh`.
6. Record the commands in `README.md` (Test section) and in `backend/AGENTS.md`.

**Acceptance.** `ruff format --check backend scripts` and `ruff check backend scripts` exit 0.
The full backend suite passes with the same test count as before the package (record both
numbers). `alembic check` reports no drift. No test file was weakened.

**Not in this package.** Renaming variables, restructuring functions, type-checking with mypy.
Those belong to Q3 and Q4.

### Q2 · Frontend linter, formatter and strict types

Size M. Depends on nothing.

**Goal.** All TypeScript and browser-check code is formatted by Prettier, passes ESLint, and
contains no `any`.

**Build.**

1. Dev dependencies (exact versions, lock file updated): `eslint`, `typescript-eslint`,
   `eslint-plugin-react-hooks`, `eslint-plugin-jsx-a11y`, `prettier`. Flat config
   `frontend/eslint.config.js` with the recommended type-checked preset plus
   `@typescript-eslint/no-explicit-any: error`, `react-hooks/exhaustive-deps: error`,
   `eqeqeq`, `no-console` (allow `warn`, `error`). Prettier: `printWidth: 110`, double quotes,
   semicolons, trailing commas.
2. **Commit 1 — mechanical:** `prettier --write "frontend/src/**/*.{ts,tsx,css}" "e2e/*.mjs"`.
   No hand edits. Typecheck, unit tests and build must pass.
3. **Following commits — remove every `any`** (56 occurrences today:
   `grep -rn ": any\|as any\|<any" frontend/src`). For each API call add a response type that
   mirrors `docs/API.md` and pass it as `api<Type>(...)`. Change the default generic of `api`
   in `frontend/src/api.ts` from `any` to `unknown` last, so the compiler finds what remains.
   Catch blocks use `unknown` and a shared `errorMessage(e)` helper.
4. Fix the remaining ESLint findings by rule, one rule per commit. A hook-dependency finding is
   a possible bug: read the effect, fix the cause, do not just add the dependency.
5. `tsconfig.json`: confirm `strict`, add `noUncheckedIndexedAccess` and
   `noImplicitOverride`; fix what they find.
6. Add `npm run lint` (`eslint . && prettier --check …`) and call it from `scripts/verify.sh`
   before the typecheck.

**Acceptance.** `npm run lint`, `npm run typecheck`, `npx vitest run` and `npm run build` pass.
`grep -rn ": any\|as any\|<any" frontend/src` prints nothing. `scripts/verify.sh --e2e` passes
with the same number of browser checks as before (record both numbers).

**Not in this package.** Visual changes, new components, renaming for readability (Q3).

### Q3 · Readable rewrite of compressed modules

Size L. Depends on Q1, Q2. Do one module per commit.

**Goal.** No module is written in the compressed style described in
[standards.md §1](../development/standards.md#1-known-debt-you-must-not-copy): descriptive
names, one idea per line, helper functions with docstrings, behaviour unchanged.

**Build.** For each module below: read its tests first; rewrite function by function keeping
the public names, routes, response shapes and error codes identical; run that module's tests
after each function. Order (worst first):

- Backend: `api/dashboard.py`, `api/task_board_conversion.py`, `api/task_conversion.py`,
  `api/task_comments.py`, `api/task_assignment.py`, `api/alert_preferences.py`, `task_events.py`,
  `task_history.py`, then any file where `ruff check --select PLR0912,PLR0915,C901` still reports.
- Backend tests in the same style: `test_dashboard.py`, `test_task_*.py`,
  `test_chat_threads.py`, `test_chat_attachments.py`, `test_alert_preferences.py`.
- Frontend: `pages/Dashboard.tsx`, `pages/MyTasks.tsx`, `pages/Todos.tsx`,
  `pages/AlertPreferences.tsx`, `components/Task*.tsx`, `components/Chat*.tsx`,
  `components/ConversationTask.tsx`, `taskUpdates.ts`.
- Browser checks: every `e2e/*.mjs` — extract shared `login`, `call` and `check` helpers into
  `e2e/lib/harness.mjs` first, then rewrite each suite to use them.

**Acceptance.** Test and browser-check counts unchanged and green after every commit. No public
contract changed (`git diff docs/API.md` is empty). Each rewritten file meets the limits in
standards §2.

**Not in this package.** Behaviour changes, bug fixes (record any bug you find in the handoff
entry with a failing-case description), visual changes.

### Q4 · Split oversized modules

Size M. Depends on Q3.

**Goal.** No hand-written source file is over 400 lines.

**Build.** `backend/labadda/models.py` → package `models/` with one module per domain
(`identity`, `workspace`, `content`, `board`, `chat`, `tasks`, `storage`, `operations`) and an
`__init__.py` that re-exports every name so imports elsewhere do not change.
`frontend/src/pages/Board.tsx` → `features/board/` (canvas, toolbar, snapshot dialog, list
view, hooks). `pages/Noticeboard.tsx` → `features/noticeboard/`. `api/board.py`, `realtime.py`
and `charge_reconciliation.py` → split by responsibility. Add `scripts/check_sizes.py`, which fails when a
hand-written source file exceeds 400 lines (fixtures, lock files and migrations excluded), and
call it from `verify.sh`.

**Acceptance.** `alembic check` shows no drift after the models split. All tests and browser
checks green with unchanged counts. `scripts/check_sizes.py` passes.

**Not in this package.** Behaviour changes.
