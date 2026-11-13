#!/usr/bin/env bash
# Run every browser suite in e2e/ on a fresh disposable proxy stack and print one line each.
# Usage: scripts/e2e-all.sh [suite...]    e.g. scripts/e2e-all.sh help setup-checklist
# Needs a built frontend (npm run build) and Chromium (LABADDA_CHROMIUM, default /usr/bin/chromium).
# Suites mutate data, so each gets its own stack; the stack lock keeps parallel workers apart.
# Every suite covers both the root and the /labadda-staging instance on its own.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
ALL=(personal-board accessibility admin-console alert-preferences audit capabilities capacity-proposals chat-attachments
  chat-threads collaboration-review console-activity console-backups console-broadcast console-health console-overview
  content-charges dashboard feedback flows governance help inspection-view inventory-jobs org-chart people
  people-authority people-changes people-import people-import-excel people-scheduled preview-observations
  preview-reconciliation-view profile research-day setup-checklist storage-inventory task-assignment
  task-board-reference task-comments task-conversion task-updates todos ui-kit unit-admin
  upload-receipts upload-recovery-ui welcome workspace-usage)
SUITES=("${@:-${ALL[@]}}")
ORIGIN=http://127.0.0.1:8080
PG="${LABADDA_PG:-postgresql+psycopg://labadda:labadda-dev@localhost:5432}"
RUN="${LABADDA_RUN_DIR:-$ROOT/var/proxy-stack}"
OUT="${LABADDA_E2E_OUT:-$(mktemp -d)}"

# cli root|staging <labadda args>: the operator command against one instance's disposable database.
cli() {
  local name=$1 db=labadda_e2e_root base=""; shift
  [ "$name" = staging ] && db=labadda_e2e_prefix base=/labadda-staging
  ( cd backend && LABADDA_ENV=test LABADDA_INSTANCE="$name" LABADDA_BASE_PATH="$base" \
      LABADDA_DATABASE_URL="$PG/$db" LABADDA_ASSET_DIR="$RUN/$name/assets" \
      LABADDA_STATUS_DIR="$RUN/$name/status" "${LABADDA_PYTHON:-$ROOT/.venv/bin}/labadda" "$@" )
}
both() { for n in root staging; do "$@" "$n"; done; }
node_suite() { node "e2e/$1.mjs" "${@:2}"; }

# Suites that read what an earlier operator step left behind get that step here.
prep() {
  case $1 in
    inspection-view) node_suite governance "$ORIGIN" "$OUT/prep" >/dev/null && both cli_run inspect-storage ;;
    preview-reconciliation-view) both cli_run reconcile-previews --max-assets 100 ;;
    storage-inventory)
      # An unreferenced candidate must sit in the shard folder named by its first two characters.
      for n in root staging; do mkdir -p "$RUN/$n/assets/pr"; : >"$RUN/$n/assets/pr/private-fixture-label-0000.bin"; done
      both cli_run inventory-storage ;;
    collaboration-review) node_suite research-day "$ORIGIN" "$OUT/prep" --synthetic-instance >/dev/null ;;
    inventory-jobs) both jobs_fixture ;;
  esac
}
cli_run() { local name=${@: -1}; cli "$name" "${@:1:$#-1}" >/dev/null; }
jobs_fixture() {
  local db=labadda_e2e_root; [ "$1" = staging ] && db=labadda_e2e_prefix
  ( cd backend && LABADDA_ENV=test LABADDA_INSTANCE="$1" LABADDA_DATABASE_URL="$PG/$db" \
      LABADDA_ASSET_DIR="$RUN/$1/assets" ../.venv/bin/python ../e2e/inventory-jobs-fixture.py >/dev/null )
}

invoke() { # origin and synthetic flags differ between suites; everything else takes an output folder
  local s=$1 shots="$OUT/$1"
  case $s in
    personal-board) LABADDA_E2E_SHOTS="$shots" node_suite personal-board ;;
    flows) node_suite flows ;;
    accessibility|content-charges|governance|upload-receipts|upload-recovery-ui)
      node_suite "$s" "$ORIGIN" "$shots" ;;
    research-day|collaboration-review) node_suite "$s" "$ORIGIN" "$shots" --synthetic-instance ;;
    *) node_suite "$s" "$shots" ;;
  esac
}

run_suite() {
  [ -f "e2e/$1.mjs" ] || { echo "no such suite: $1" >&2; return 2; }
  if [ "$1" != ui-kit ]; then # the component gallery runs on its own dev server
    # Backup receipts and stray files from an earlier suite would change what the next one sees.
    rm -rf "$RUN"/{root,staging}/status "$RUN"/{root,staging}/assets
    mkdir -p "$RUN"/{root,staging}/{status,assets}
    scripts/proxy-stack.sh start >/dev/null 2>&1 || { echo "stack failed to start" >&2; return 2; }
    prep "$1" || { scripts/proxy-stack.sh stop; echo "fixture step failed" >&2; return 2; }
  fi
  invoke "$1"; local rc=$?
  [ "$1" = ui-kit ] || scripts/proxy-stack.sh stop
  return $rc
}

fails=0
printf '%-30s %-5s %s\n' SUITE RESULT CHECKS
for s in "${SUITES[@]}"; do
  mkdir -p "$OUT/$s"
  # Takes the stack lock itself: wrapping this script in another flock on the same file deadlocks.
  (
    exec 9>/tmp/labadda-e2e.lock
    until flock -w 300 9; do
      echo "e2e-all: still waiting for /tmp/labadda-e2e.lock. Do not wrap this script in flock." >&3
    done
    run_suite "$s"
  ) 3>&2 >"$OUT/$s.log" 2>&1
  rc=$?
  n=$(grep -c '^PASS' "$OUT/$s.log")
  if [ $rc -eq 0 ]; then r=PASS; else r=FAIL; fails=$((fails + 1)); fi
  printf '%-30s %-5s %s\n' "$s" "$r" "$n"
done
echo "logs and screenshots: $OUT"
[ $fails -eq 0 ] || { echo "$fails suite(s) failed; see their .log files"; exit 1; }
