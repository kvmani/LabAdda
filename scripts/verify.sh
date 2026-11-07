#!/usr/bin/env bash
# Single local verification entry point. CI runs the same commands.
#   scripts/verify.sh            backend tests, frontend typecheck/unit tests/build
#   scripts/verify.sh --e2e      also run browser flows through nginx (root + prefix)
# Requires a disposable PostgreSQL reachable via LABADD_TEST_DATABASE_URL (see README).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="${LABADD_PYTHON:-$ROOT/.venv/bin}"

echo "== backend: migrations, policy, API, realtime (pytest) =="
( cd "$ROOT/backend" && "$PY/python" -m pytest -q -p no:cacheprovider )

echo "== backend: model/migration drift =="
( cd "$ROOT/backend" && LABADD_DATABASE_URL="${LABADD_TEST_DATABASE_URL:-postgresql+psycopg://labadd:labadd-dev@localhost:5432/labadd_test}" "$PY/alembic" check )

echo "== frontend: typecheck, unit tests, production build =="
( cd "$ROOT/frontend" && npm run --silent typecheck && npx vitest run && npm run --silent build )

if [[ "${1:-}" == "--e2e" ]]; then
  echo "== browser flows through nginx (T03 + P1/P2/P3 flows) =="
  "$ROOT/scripts/proxy-stack.sh" start
  trap '"$ROOT/scripts/proxy-stack.sh" stop' EXIT
  node "$ROOT/e2e/flows.mjs" "http://127.0.0.1:${LABADD_PROXY_PORT:-8080}" "" /labadd-staging
fi
echo "verify: OK"
