#!/usr/bin/env bash
# Start a root instance and a prefixed instance behind a local nginx (T03).
# The test stack uses a 35 s panel idle window so the browser flow can observe the idle lock.
# Usage: scripts/proxy-stack.sh start|stop   (uses disposable databases)
# LABADDA_PROXY_TLS=1 serves https/wss with a throwaway CA at $RUN/tls/ca.crt and Secure cookies.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RUN="${LABADDA_RUN_DIR:-$ROOT/var/proxy-stack}"
PY="${LABADDA_PYTHON:-$ROOT/.venv/bin}"
PG="${LABADDA_PG:-postgresql+psycopg://labadda:labadda-dev@localhost:5432}"
PORT="${LABADDA_PROXY_PORT:-8080}"
TLS="${LABADDA_PROXY_TLS:-0}"
SCHEME=http; [ "$TLS" = 1 ] && SCHEME=https
SECURE=false; [ "$TLS" = 1 ] && SECURE=true

make_tls() { # throwaway CA + server certificate for 127.0.0.1/localhost; never for real deployments
  mkdir -p "$RUN/tls" && cd "$RUN/tls"
  openssl req -x509 -newkey rsa:2048 -nodes -days 2 -subj "/CN=LabAdda rehearsal CA" \
    -keyout ca.key -out ca.crt >/dev/null 2>&1
  openssl req -newkey rsa:2048 -nodes -subj "/CN=127.0.0.1" -keyout server.key -out server.csr >/dev/null 2>&1
  printf 'subjectAltName=IP:127.0.0.1,DNS:localhost\nbasicConstraints=CA:FALSE\nextendedKeyUsage=serverAuth\n' >ext.cnf
  openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial -days 2 -extfile ext.cnf \
    -out server.crt >/dev/null 2>&1
  chmod 600 ca.key server.key
  cd - >/dev/null
}

start_instance() { # name port prefix db
  mkdir -p "$RUN/$1"
  ( cd "$ROOT/backend"
    export LABADDA_ENV=test LABADDA_INSTANCE="$1" LABADDA_BASE_PATH="$3" LABADDA_DATABASE_URL="$PG/$4" \
           LABADDA_COOKIE_NAME="labadda_$1" LABADDA_ASSET_DIR="$RUN/$1/assets" LABADDA_REMINDER_INTERVAL_SECONDS=2 LABADDA_PANEL_IDLE_SECONDS=35 \
           LABADDA_COOKIE_SECURE="$SECURE" \
           LABADDA_LOGIN_ATTEMPTS_PER_WINDOW="${LABADDA_LOGIN_ATTEMPTS_PER_WINDOW:-10}"
    "$PY/labadda" migrate >/dev/null
    "$PY/labadda" seed --reset >/dev/null
    nohup "$PY/labadda" serve --port "$2" >"$RUN/$1/server.log" 2>&1 &
    echo $! >"$RUN/$1/pid" )
}

stop_stack() {
  nginx -c "$RUN/nginx.conf" -p "$RUN" -s stop 2>/dev/null || true
  for n in root staging; do [ -f "$RUN/$n/pid" ] && kill "$(cat "$RUN/$n/pid")" 2>/dev/null || true; done
  sleep 1
}

case "${1:-start}" in
  start)
    stop_stack  # a previous run may still hold the ports
    mkdir -p "$RUN/tmp"
    start_instance root 8001 "" labadda_e2e_root
    start_instance staging 8002 /labadda-staging labadda_e2e_prefix
    SSL=""; CERTS=""; CURL=(curl -fsS)
    if [ "$TLS" = 1 ]; then
      make_tls
      SSL=ssl
      CERTS="ssl_certificate $RUN/tls/server.crt; ssl_certificate_key $RUN/tls/server.key;"
      CURL+=(--cacert "$RUN/tls/ca.crt")
    fi
    sed -e "s#__RUN__#$RUN#g" -e "s#__PORT__#$PORT#g" -e "s#__DIST__#$ROOT/frontend/dist#g" \
      -e "s#__SSL__#$SSL#g" -e "s#__TLS_CERTS__#$CERTS#g" \
      "$ROOT/deploy/nginx/local-test.conf" >"$RUN/nginx.conf"
    nginx -c "$RUN/nginx.conf" -p "$RUN"
    for url in "$SCHEME://127.0.0.1:$PORT/healthz" "$SCHEME://127.0.0.1:$PORT/labadda-staging/readyz"; do
      for _ in $(seq 1 50); do "${CURL[@]}" "$url" >/dev/null 2>&1 && break; sleep 0.2; done
      "${CURL[@]}" "$url"; echo
    done ;;
  stop)
    stop_stack ;;
esac
