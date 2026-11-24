#!/usr/bin/env bash
# One command for every routine server job. Run with no arguments to see the list.
#   sudo labadda-admin <command> [options] [--site NAME]
# Commands:
#   status [--json]           state of the site: services, health, last backup, disk, version
#   check                     quiet health check for monitoring: exit 0 healthy, 1 not (prints why)
#   doctor                    the application's own checks, in plain words
#   logs [LINES]              the last LINES lines (default 100) of the LabAdda service log
#   restart                   restart LabAdda and wait until it answers again
#   backup [options]          take a verified backup now (same options as labadda-backup-now)
#   backups                   list the backups kept on this server, newest first
#   upgrade [options]         upgrade to a new release (same options as labadda-upgrade)
#   restore [options]         restore a backup into a separate test copy (labadda-restore)
#   reattach-nginx [options]  put LabAdda back into a shared nginx site (labadda-reattach-nginx)
#   support-report [DIR]      save status, doctor and version (no secrets, no content) to one file
set -euo pipefail
SELF="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
# shellcheck source=lib/common.sh
source "$SELF/lib/common.sh"

usage() { sed -n '2,17p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; }

COMMAND=${1:-help}
(($#)) && shift
# Commands that only pass their options on are handed every argument unchanged.
case $COMMAND in
  status) exec bash "$SELF/status.sh" "$@" ;;
  backup) exec bash "$SELF/backup-now.sh" "$@" ;;
  upgrade) exec bash "$SELF/upgrade.sh" "$@" ;;
  restore) exec bash "$SELF/restore.sh" "$@" ;;
  reattach-nginx) exec bash "$SELF/reattach-nginx.sh" "$@" ;;
  help | -h | --help) usage; exit 0 ;;
  check | doctor | logs | restart | backups | support-report) ;;
  *) usage >&2; die "Unknown command '$COMMAND'." ;;
esac

ARGS=()
while (($#)); do
  case $1 in
    --site) SITE=$2; shift ;;
    *) ARGS+=("$1") ;;
  esac
  shift
done
set_paths
[[ -f $SITE_JSON ]] || die "Site '$SITE' is not installed here (no $SITE_JSON)."
load_site_identity
# The answers file is root-only; the 15-minute check runs as the service account without it.
[[ ! -r $ANSWERS_FILE ]] || load_answers "$ANSWERS_FILE"

doctor() {
  [[ $(current_version) != none ]] || die "No release is installed."
  ( cd "$INSTANCE_ROOT/current/backend" \
    && as_service "$INSTANCE_ROOT/current/venv/bin/python" -m labadda.cli doctor --env-file "$ENV_FILE" )
}

# Prints one line per problem; returns non-zero when any check failed.
check() {
  local problems=()
  [[ $(svc is-active "$UNIT" 2>/dev/null) == active ]] || problems+=("service $UNIT is not running")
  operations probe --direct >/dev/null 2>&1 || problems+=("LabAdda does not answer on its own port")
  operations probe >/dev/null 2>&1 \
    || problems+=("$(site_url) could not be confirmed through nginx (nginx down or certificate not trusted here)")
  [[ ! -e $INSTANCE_ROOT/traffic/maintenance ]] || problems+=("the site is in maintenance (closed to users)")
  local facts age
  facts=$("$PYTHON" "$TOOLS_DIR/scripts/install_helpers.py" status --status-dir "$INSTANCE_ROOT/status" 2>/dev/null || true)
  age=$("$PYTHON" -c 'import json,sys
try: age = json.loads(sys.argv[1]).get("age_hours")
except ValueError: age = None
print("" if age is None else age)' "$facts")
  if [[ -z $age ]]; then problems+=("no backup is recorded")
  elif (($(printf '%.0f' "$age") > 36)); then problems+=("the last backup is $age hours old"); fi
  if ((${#problems[@]})); then printf 'NOT HEALTHY: %s\n' "${problems[@]}"; return 1; fi
  say "HEALTHY: service running, answering, not in maintenance, backup $age hours old"
}

logs() {
  local lines=${ARGS[0]:-100}
  [[ $lines =~ ^[0-9]{1,5}$ ]] || die "LINES must be a number, for example: labadda-admin logs 200"
  if is_user_scope; then
    as_service env XDG_RUNTIME_DIR="/run/user/$(id -u "$SERVICE_USER")" journalctl --user -u "$UNIT" -n "$lines" --no-pager
  else
    journalctl -u "$UNIT" -n "$lines" --no-pager
  fi
}

restart() {
  need_root
  step "Restarting $UNIT"
  run svc restart "$UNIT"
  ((DRY_RUN)) && return 0
  wait_for_health 90 || die "LabAdda did not answer within 90 seconds. See: labadda-admin logs"
  ok "LabAdda answers again"
}

backups() {
  [[ -d $BACKUP_ROOT ]] || { say "No backups folder yet ($BACKUP_ROOT)."; return 0; }
  local found=0 dir
  printf '  %-40s %8s  %s\n' "Backup" "Size" "Taken"
  while IFS= read -r dir; do
    found=1
    printf '  %-40s %8s  %s\n' "${dir##*/}" "$(du -sh "$dir" | cut -f1)" "$(date -r "$dir" '+%Y-%m-%d %H:%M')"
  done < <(find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d -printf '%T@ %p\n' | sort -rn | cut -d' ' -f2-)
  ((found)) || say "  (none kept on this server)"
  say "Restore one into a test copy with: sudo labadda-admin restore --bundle <folder> --manifest-sha256 <digest>"
}

support_report() {
  local dir=${ARGS[0]:-$PWD} stamp out
  stamp=$(date '+%Y%m%d-%H%M%S')
  out="$dir/labadda-support-$SITE-$stamp.txt"
  [[ -d $dir && -w $dir ]] || die "Cannot write to $dir"
  {
    say "LabAdda support report for site '$SITE', $(date '+%Y-%m-%d %H:%M %Z')"
    say "Contains service states, checks and versions only: no passwords, keys or user content."
    say ""; say "== status"; bash "$SELF/status.sh" --site "$SITE" 2>&1 || true
    say ""; say "== check"; check 2>&1 || true
    say ""; say "== doctor"; doctor 2>&1 || true
    say ""; say "== operating system"; (. /etc/os-release && say "$PRETTY_NAME") || true; uname -r
    say ""; say "== recent releases"; ls -1t "$INSTANCE_ROOT/releases" 2>/dev/null | head -5 || true
  } >"$out"
  chmod 0600 "$out"
  ok "saved $out (send this file when asking for help)"
}

case $COMMAND in
  check) check ;;
  doctor) doctor ;;
  logs) logs ;;
  restart) restart ;;
  backups) backups ;;
  support-report) support_report ;;
esac
