#!/usr/bin/env bash
# One-screen state of the LabAdda site: services, health, last backup, disk, version.
# Send its output (and the output of the doctor) when you ask for help. Prints no secrets.
#   sudo labadda-status [--site NAME] [--json]
# --json prints the same facts as one JSON object for monitoring scripts.
set -uo pipefail
SELF="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
# shellcheck source=lib/common.sh
source "$SELF/lib/common.sh"
JSON=0
while (($#)); do case $1 in --site) SITE=$2; shift ;; --json) JSON=1 ;; *) die "Unknown option $1" ;; esac; shift; done
set_paths
[[ -f $SITE_JSON ]] || die "Site '$SITE' is not installed here (no $SITE_JSON)."
load_site_identity
set +e

line() { printf '  %-18s %s\n' "$1" "$2"; }
active() { "$SYSTEMCTL" is-active "$1" 2>/dev/null || true; }
own_active() { svc is-active "$1" 2>/dev/null || true; }
VERSION_NOW=$(current_version)
facts=$("$PYTHON" "$TOOLS_DIR/scripts/install_helpers.py" status --status-dir "$INSTANCE_ROOT/status" 2>/dev/null)
[[ -n $facts ]] || facts='{}'
[[ ! -f $ANSWERS_FILE ]] || load_answers "$ANSWERS_FILE"
if ((JSON)); then
  direct=false; web=false; maintenance=false
  operations probe --direct >/dev/null 2>&1 && direct=true
  operations probe >/dev/null 2>&1 && web=true
  [[ -e $INSTANCE_ROOT/traffic/maintenance ]] && maintenance=true
  "$PYTHON" - "$facts" "$SITE" "$VERSION_NOW" "$(own_active "$UNIT")" "$(active nginx)" "$(active postgresql)" \
    "$(own_active "labadda-backup@$SITE.timer")" "$direct" "$web" "$maintenance" "$INSTANCE_ROOT" "$BACKUP_ROOT" <<'PYTHON'
import json
import shutil
import sys

facts, site, release, service, nginx, postgresql, timer, direct, web, maintenance, data, backups = sys.argv[1:]
try:
    backup = json.loads(facts)
except ValueError:
    backup = {}


def free(path):
    try:
        return shutil.disk_usage(path).free
    except OSError:
        return None


print(json.dumps({
    "site": site,
    "release": release,
    "service": service,
    "nginx": nginx,
    "postgresql": postgresql,
    "backup_timer": timer,
    "answers_directly": direct == "true",
    "answers_through_web": web == "true",
    "maintenance": maintenance == "true",
    "last_backup": backup.get("backup"),
    "last_backup_age_hours": backup.get("age_hours"),
    "last_backup_check": backup.get("verification"),
    "data_free_bytes": free(data),
    "backups_free_bytes": free(backups),
}, indent=2))
PYTHON
  exit 0
fi
say "LabAdda status for site '$SITE' on $(hostname) at $(date '+%Y-%m-%d %H:%M %Z')"
say ""; say "Version"
line "release" "$VERSION_NOW"
if [[ $VERSION_NOW != none ]]; then
  line "application" "$(sed -n 's/^__version__ = "\(.*\)"/\1/p' "$INSTANCE_ROOT/current/backend/labadda/__init__.py")"
  line "build commit" "$("$PYTHON" -c 'import json,sys;print(json.load(open(sys.argv[1]))["commit"][:12])' "$INSTANCE_ROOT/current/manifest.json")"
fi
say ""; say "Services"
line "labadda" "$(own_active "$UNIT") ($SERVICE_SCOPE scope, account $SERVICE_USER)"; line "nginx" "$(active nginx)"; line "postgresql" "$(active postgresql)"
line "nightly backup" "$(own_active "labadda-backup@$SITE.timer")"
say ""; say "Health"
if operations probe --direct >/dev/null 2>&1; then line "app (private)" "ready"; else line "app (private)" "NOT ANSWERING"; fi
if operations probe >/dev/null 2>&1; then line "web address" "$(site_url) answers"
elif is_shared_http; then line "web address" "NOT ANSWERING at $(site_url) - if the other application rewrote its nginx site, run: sudo labadda-reattach-nginx"
else line "web address" "not confirmed (self-signed certificate or nginx down)"; fi
[[ -e $INSTANCE_ROOT/traffic/maintenance ]] && line "maintenance" "ON - site closed to users (an upgrade or backup was interrupted)"
say ""; say "Backups"
line "last backup" "$("$PYTHON" -c 'import json,sys;f=json.loads(sys.argv[1]);print("unknown (none recorded)" if f.get("age_hours") is None else "%s, %s hours ago, check %s"%(f["backup"],f["age_hours"],f["verification"]))' "$facts")"
line "kept on server" "$(find "$BACKUP_ROOT" -maxdepth 1 -mindepth 1 -type d 2>/dev/null | wc -l) backup(s)"
say ""; say "Disk"
line "data" "$(df -h --output=avail,pcent "$INSTANCE_ROOT" | tail -1 | awk '{print $1" free ("$2" used)"}')"
line "backups" "$(df -h --output=avail,pcent "$BACKUP_ROOT" 2>/dev/null | tail -1 | awk '{print $1" free ("$2" used)"}')"
say ""; say "More: sudo labadda doctor output -> $INSTANCE_ROOT/current/venv/bin/python -m labadda.cli doctor --env-file $ENV_FILE"
