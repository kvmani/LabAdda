#!/usr/bin/env bash
# Start a root instance and a prefixed instance behind a local nginx (T03).
# Usage: scripts/proxy-stack.sh start|stop   (uses disposable databases)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RUN="${LABADDA_RUN_DIR:-$ROOT/var/proxy-stack}"
PY="${LABADDA_PYTHON:-$ROOT/.venv/bin}"
PG="${LABADDA_PG:-postgresql+psycopg://labadda:labadda-dev@localhost:5432}"
PORT="${LABADDA_PROXY_PORT:-8080}"

start_instance() { # name port prefix db
  mkdir -p "$RUN/$1"
  ( cd "$ROOT/backend"
    export LABADDA_ENV=test LABADDA_INSTANCE="$1" LABADDA_BASE_PATH="$3" LABADDA_DATABASE_URL="$PG/$4" \
           LABADDA_COOKIE_NAME="labadda_$1" LABADDA_ASSET_DIR="$RUN/$1/assets" LABADDA_REMINDER_INTERVAL_SECONDS=2
    "$PY/labadda" migrate >/dev/null
    "$PY/labadda" seed --reset >/dev/null
    nohup "$PY/labadda" serve --port "$2" >"$RUN/$1/server.log" 2>&1 &
    echo $! >"$RUN/$1/pid" )
}

case "${1:-start}" in
  start)
    mkdir -p "$RUN/tmp"
    start_instance root 8001 "" labadda_e2e_root
    start_instance staging 8002 /labadda-staging labadda_e2e_prefix
    sed -e "s#__RUN__#$RUN#g" -e "s#__PORT__#$PORT#g" -e "s#__DIST__#$ROOT/frontend/dist#g" \
      "$ROOT/deploy/nginx/local-test.conf" >"$RUN/nginx.conf"
    nginx -c "$RUN/nginx.conf" -p "$RUN"
    for url in "http://127.0.0.1:$PORT/healthz" "http://127.0.0.1:$PORT/labadda-staging/readyz"; do
      for _ in $(seq 1 50); do curl -fsS "$url" >/dev/null 2>&1 && break; sleep 0.2; done
      curl -fsS "$url"; echo
    done ;;
  stop)
    nginx -c "$RUN/nginx.conf" -p "$RUN" -s stop 2>/dev/null || true
    for n in root staging; do [ -f "$RUN/$n/pid" ] && kill "$(cat "$RUN/$n/pid")" 2>/dev/null || true; done ;;
esac
