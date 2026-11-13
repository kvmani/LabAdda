# Engineering standards and recipes

Read this before writing code. It applies to every change. [AGENTS.md](../../AGENTS.md) holds the
rules that are never broken; this file tells you how to write code that meets them.

The goal is code a new maintainer can read top to bottom once and trust: plain, typed, tested,
and no longer than the job needs.

## 1. Known debt you must not copy

Parts of the existing code were written in a compressed style: several statements on one line
joined with `;`, no spaces around operators, one-letter names, 200-character lines, `any` in
TypeScript. Examples are `backend/labadda/api/dashboard.py`, `frontend/src/pages/Dashboard.tsx`
and most files in `e2e/`. This is debt, scheduled for removal in work packages Q1–Q4 of
[the plan](../plan/quality.md). Until then:

- **Do not imitate that style**, even inside a file that uses it.
- New files follow this document from the first line.
- When a card makes you edit a compressed function, rewrite that one function in the standard
  style in the same commit. Do not reformat the rest of the file; the Q packages do that in
  dedicated mechanical commits so reviews stay readable.

## 2. Rules for all code

1. **One statement per line.** No `;`-joined statements, no multiple assignments on one line.
2. **Names say what the thing is.** `membership`, `workspace`, `transfer_plan` — not `m`, `ws`,
   `tp`. Loop counters and well-known short forms (`db`, `id`, `e` for a caught error) are fine.
3. **Limits.** Line ≤ 110 characters. Function ≤ 60 lines. File ≤ 400 lines. At a limit, split
   by responsibility, not arbitrarily.
4. **No dead weight.** No unused imports, parameters, variables, exports, feature flags or
   files. No commented-out code. No "just in case" options that no caller uses.
5. **No duplicate logic.** Search for an existing helper before writing one
   (`grep -rn "def <verb>" backend/labadda`, `grep -rn "export function" frontend/src`).
   If you need the same ten lines twice, extract them once, next to their subject.
6. **Fail clearly.** Raise the typed errors in `backend/labadda/errors.py` with a stable code
   and a sentence an office user understands. Never swallow an exception silently; never use a
   bare `except:` or `except Exception: pass`.
7. **Comments explain why.** A constraint, an invariant, a non-obvious ordering. Never restate
   the code, never describe the history of a change, never leave notes to the reviewer.
8. **Docstrings.** One line on every module and every public function saying what it guarantees.
9. **No secrets or content in logs.** Log event codes, IDs and counts. Never tokens, message
   text, note text, file names or request bodies.

## 3. Backend (Python 3.12, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL 16)

### Layout

| Path | Holds |
| --- | --- |
| `backend/labadda/api/<feature>.py` | Routers: parse, authorize, call domain functions, serialize |
| `backend/labadda/<feature>.py` | Domain logic that more than one router or the scheduler uses |
| `backend/labadda/policy.py` | The only place that decides who can read, write or moderate |
| `backend/labadda/deps.py` | Session loading, CSRF and origin checks, `current_actor`, `require_admin` |
| `backend/labadda/memberships.py`, `identity_locks.py` | Membership writes and their locks |
| `backend/labadda/audit.py` | `audit.record(...)` for identity, membership, hierarchy, authority |
| `backend/labadda/errors.py` | `NotFound`, `Forbidden`, `Conflict`, `Invalid`, `TooMany` |
| `backend/labadda/models.py` | SQLAlchemy models (split into a `models/` package in Q4) |
| `backend/migrations/versions/NNNN_<name>.py` | One migration per schema change, numbered |
| `backend/tests/test_<feature>.py` | Tests against a real disposable PostgreSQL |

### Recipe: add an endpoint

1. Write the contract first in [docs/API.md](../API.md): method, path, who may call it, request
   fields with bounds, response shape, every error code.
2. Define Pydantic request models with explicit bounds (`Field(min_length=1, max_length=120)`).
   Validate enums with `Literal[...]`. Reject unknown fields on admin and people endpoints
   (`model_config = ConfigDict(extra="forbid")`).
3. Authorize with a dependency: `current_actor` for members, `require_admin` (or the capability
   dependency introduced in package A1) for administration. Never accept a panel session unless
   the endpoint is a board endpoint.
4. Load the resource, then check access through `policy`. If the actor cannot read it, raise
   `NotFound()` — the same response as a missing ID.
5. For writes: take the relevant lock (`memberships.lock_workspace_roles`,
   `memberships.lock_admin_roles`, `identity_locks`), re-read under the lock, check the expected
   revision, apply, `audit.record(...)` when identity/membership/hierarchy/authority changes,
   then `db.commit()`. Notify the realtime hub **after** the commit.
6. Return plain JSON through a `_<thing>_json` serializer. Dates are ISO 8601 UTC via
   `serialize.iso`. Lists are paginated with a stable order and a bounded `limit`.
7. Register the router in `backend/labadda/app.py`.

```python
class StaffStatusChange(BaseModel):
    """Request body for changing a person's employment status."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["active", "on_leave", "retired", "left"]
    effective_on: date
    reason: str = Field(min_length=3, max_length=500)
    revision: int = Field(ge=1)


@router.post("/people/{user_id}/status")
def change_status(
    user_id: uuid.UUID,
    body: StaffStatusChange,
    actor: Actor = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Change a person's employment status; the caller must hold the current revision."""
    memberships.lock_admin_roles(db)
    person = db.get(User, user_id, with_for_update=True)
    if person is None:
        raise NotFound()
    if person.revision != body.revision:
        raise Conflict("stale_revision", "This record changed. Reload and review it again.")
    ...
```

### Recipe: change the schema

1. Add the model change and a new migration `NNNN_<name>.py` (next number, never edit an old
   one). Additive first: new nullable column or new table, backfill in the migration, then
   constraints.
2. `downgrade()` must raise if it would drop populated data. Copy the guard from
   `0003_collaborative_groups.py` or `0025_notification_preferences.py`.
3. Add or extend `backend/tests/test_migrations.py`; run `alembic check` (part of `verify.sh`).
4. If the table holds user data, extend `backend/tests/test_recovery_integration.py` so backup
   and restore are proven to preserve it.

### Fixture data

All fixture, seed, e2e, help and documentation examples use Indian personal names and Indian
national-research-laboratory units, groups and projects. The accounts and units are listed in
[fixture-names.md](fixture-names.md); `scripts/check_docs.py` fails if a retired name returns.

### Recipe: test a feature

Use the fixtures in `backend/tests/conftest.py`: `as_user("asha")` returns a signed-in client;
`ids` holds fixture workspace and user IDs. Every feature test file covers:

- the success path, reloaded from the server, not just the response of the write;
- **the denial matrix**: `chitra` (sibling section), `deepa` (parent division only, for child
  content), `admin` (no content grant), `esha` (project guest), `farhan` (deactivated), a signed-out
  client, and a panel session (`headers={"X-LabAdda-Panel": "1"}`) — each must get 401, 403 or
  the uniform 404 as the contract says;
- validation bounds (too long, wrong type, unknown field);
- retry and conflict behaviour where the contract defines it;
- for admin and people features: the audit row exists with actor, target, before/after and
  reason, and **no content field appears in any admin response**.

One behaviour per test, named `test_<subject>_<condition>_<expected>`. Assertions on separate
lines. No sleeps; inject the clock (`now=`) as `scheduler.process_due_reminders` does.

### Other backend rules

- SQL goes through SQLAlchemy `select(...)` with bound parameters. No string-built SQL.
- Aggregations for dashboards run as bounded queries with a statement timeout, never per-row
  loops, and never lock content tables.
- Background work goes through the existing scheduler tick (`scheduler.py`); it must be safe to
  run twice and safe to crash midway. Do not add processes, thread pools or brokers.
- Settings are read once in `config.py` from `LABADDA_*` variables, validated at start-up, and
  documented in `deploy/labadda.env.example`.

## 4. Frontend (React 18, TypeScript, Vite)

### Layout

| Path | Holds |
| --- | --- |
| `frontend/src/ui/` | Shared components and tokens (created in package U1). Use these first |
| `frontend/src/pages/` | One file per route; composes components, owns no reusable logic |
| `frontend/src/features/<feature>/` | Components, hooks and types for one feature (new code) |
| `frontend/src/api.ts` | The only `fetch` wrapper. Never call `fetch` directly |
| `frontend/src/types.ts`, `features/*/types.ts` | Response types that mirror `docs/API.md` |
| `frontend/src/help/` | In-app help pages (created in package H1) |
| `e2e/*.mjs` | Browser checks run at `/` and `/labadda-staging` |

### Recipe: add a screen

1. Types first: add the response types that mirror the API contract. Call `api<Type>(path)`;
   never leave the generic to default to `any`.
2. Build from `frontend/src/ui` components (page header, table, dialog, form field, status
   pill, empty state). If a component is missing, add it to `ui/` with its states, then use it.
   Follow [ui-design-system.md](ui-design-system.md) for layout, spacing, wording and charts.
3. Handle every state explicitly: loading (skeleton, not a spinner over stale data), empty
   (what this is and the first action), error (what failed and what to do), forbidden, offline,
   saving, saved, conflict (keep the user's draft and show the current server value).
4. Guard against stale responses with the generation-counter pattern used in
   `pages/Dashboard.tsx`: a response that arrives after the scope changed or access was revoked
   must not be rendered.
5. Destructive or audience-changing actions use a confirmation dialog that names the people and
   units affected in plain words, and require a reason where the API does.
6. Add the route in `App.tsx`, the navigation entry, the help link, and an `e2e` check.

```tsx
export function PeopleTable({ people, onOpen }: PeopleTableProps) {
  if (people.length === 0) {
    return (
      <EmptyState title="No people match these filters">
        Clear the filters, or add a person with “Add person”.
      </EmptyState>
    );
  }
  return (
    <DataTable
      caption="People"
      columns={PEOPLE_COLUMNS}
      rows={people}
      rowKey={(person) => person.id}
      onRowOpen={onOpen}
    />
  );
}
```

### Other frontend rules

- No `any`. Catch blocks use `unknown` and narrow with `e instanceof ApiError`.
- No inline styles and no new global class names; use tokens and `ui/` components.
- Effects clean up subscriptions and timers. Polling stops when the tab is hidden.
- No new runtime dependency unless the card names it. Charts are local SVG components.
- Text is real text: no images of text, no colour-only meaning, every input has a label.
- Unit-test pure logic with Vitest next to the file (`thing.test.ts`). Test user flows in `e2e/`.

### Recipe: browser check

Write `e2e/<feature>.mjs` in the readable style: named helper functions, one action per line,
`check(condition, "plain description")` for each assertion, loop over `["", "/labadda-staging"]`.
Include one axe-core accessibility scan at desktop (1400 px) and phone (390 px) width, and one
check that a user without the right role cannot reach the screen. Register the script in
`PROFILES` in `scripts/simulate.py` so the full profile runs it.

## 5. Dependencies and tools

- Python dependencies are pinned in `backend/pyproject.toml` and `backend/requirements.lock`;
  Node dependencies in `package.json` with exact versions and the lock file. Update both.
- **Dependency age policy.** Every pinned version, transitive ones included, must have been released at
  least 30 days ago so the office package mirrors have it. Run `python3.12 scripts/check_dependency_age.py`
  after any change to a lock; it lists each younger version. Re-pin to the newest version that is at least
  30 days old and compatible (for npm: `npm install --package-lock-only --before=<date 30 days ago>` in a
  scratch copy), then run `scripts/verify.sh`. The release build runs the same check and stops on failure.
- A new dependency needs: a named reason in the card, a permissive open-source licence, no
  network access at runtime, and an entry in the release licence inventory (`scripts/release.py`).
- Formatting and linting gates (Ruff, ESLint, Prettier) arrive with packages Q1 and Q2. Once a
  gate exists, never bypass it; fix the code.

## 6. Self-review before you commit

Read your own diff line by line and answer each question. If any answer is "no", fix it first.

1. Does every changed line serve the card? Is anything left over from an abandoned approach?
2. Could a member of a sibling section, a parent-only member, an administrator, a deactivated
   user or a panel session reach data through this change that they could not reach before?
3. What happens on double-click, retry after timeout, two people saving at once, and a lost
   connection mid-save?
4. Is there a test that fails if this change is reverted?
5. Would an office user understand every sentence shown on screen, including the errors?
6. Are the API contract, help page, feature guide and plan status updated in this commit?
7. Did `scripts/verify.sh` pass on this exact tree?
