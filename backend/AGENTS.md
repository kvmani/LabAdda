# Backend instructions

Read the [repository instructions](../AGENTS.md) first. This file adds only what is specific to
`backend/`. Full recipes: [standards.md §3](../docs/development/standards.md#3-backend-python-312-fastapi-sqlalchemy-2-alembic-postgresql-16).

## Where things go

- Routers in `labadda/api/<feature>.py`: parse, authorize, call domain code, serialize. Keep
  them thin.
- Domain logic shared by routers or the scheduler in `labadda/<feature>.py` (or a package for
  larger areas: `changes/`, `metrics/`, `health/`).
- Access decisions only in `labadda/policy.py`. Membership writes only through
  `labadda/memberships.py`. Audit rows only through `labadda/audit.py`.
- One Alembic migration per schema change in `migrations/versions/NNNN_<name>.py`. Never edit
  a pushed migration.
- Tests in `tests/test_<feature>.py`, against real PostgreSQL, using `as_user(...)` and `ids`.

## Always

- Request bodies are Pydantic models with explicit bounds; admin and people bodies forbid
  unknown fields.
- Out-of-scope resource → `NotFound()`. Not signed in → `Unauthenticated()`. Visible but not
  allowed → `Forbidden(code, message)`. Stale revision or digest → `Conflict(code, message)`.
- Lock, re-read, check revision, write, audit, commit — then notify the realtime hub.
- Write the denial matrix for every endpoint: sibling member, parent-only member, administrator
  without a grant, project guest, deactivated user, signed-out client, panel session.
- Admin, analytics, health and people endpoints return metadata only. Add the test that seeds
  recognisable content and asserts it is absent from every response.
- Inject the clock (`now=`) in anything time-dependent; no sleeps in tests.

## Never

- No string-built SQL, no per-row query loops in list endpoints, no unbounded `limit`.
- No new process, thread pool, broker or cache service.
- No content, tokens or request bodies in logs or audit detail.
- No compressed style (several statements per line, one-letter names). See standards §1.

## Commands

```bash
cd backend
../.venv/bin/python -m pytest tests/test_<feature>.py -q    # while iterating
../.venv/bin/python -m pytest -q                            # whole backend suite
LABADDA_DATABASE_URL=$LABADDA_TEST_DATABASE_URL ../.venv/bin/alembic check   # model/migration drift
```

Run one pytest session at a time: the fixtures recreate the test schema.
