#!/usr/bin/env bash
# One-screen state of the LabAdda site: services, health, last backup, disk, version.
# Send its output (and the output of the doctor) when you ask for help. Prints no secrets.
#   sudo labadda-status [--site NAME]
set -uo pipefail
SELF="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
# shellcheck source=lib/common.sh
source "$SELF/lib/common.sh"
while (($#)); do case $1 in --site) SITE=$2; shift ;; *) die "Unknown option $1" ;; esac; shift; done
set_paths
[[ -f $SITE_JSON ]] || die "Site '$SITE' is not installed here (no $SITE_JSON)."
set +e

line() { printf '  %-18s %s\n' "$1" "$2"; }
active() { "$SYSTEMCTL" is-active "$1" 2>/dev/null || true; }
VERSION_NOW=$(current_version)
say "LabAdda status for site '$SITE' on $(hostname) at $(date '+%Y-%m-%d %H:%M %Z')"
say ""; say "Version"
line "release" "$VERSION_NOW"
if [[ $VERSION_NOW != none ]]; then
  line "application" "$(sed -n 's/^__version__ = "\(.*\)"/\1/p' "$INSTANCE_ROOT/current/backend/labadda/__init__.py")"
  line "build commit" "$("$PYTHON" -c 'import json,sys;print(json.load(open(sys.argv[1]))["commit"][:12])' "$INSTANCE_ROOT/current/manifest.json")"
fi
say ""; say "Services"
line "labadda" "$(active "$UNIT")"; line "nginx" "$(active nginx)"; line "postgresql" "$(active postgresql)"
line "nightly backup" "$(active "labadda-backup@$SITE.timer")"
say ""; say "Health"
if operations probe --direct >/dev/null 2>&1; then line "app (private)" "ready"; else line "app (private)" "NOT ANSWERING"; fi
if operations probe >/dev/null 2>&1; then line "web address" "answers"; else line "web address" "not confirmed (self-signed certificate or nginx down)"; fi
[[ -e $INSTANCE_ROOT/traffic/maintenance ]] && line "maintenance" "ON - site closed to users (an upgrade or backup was interrupted)"
say ""; say "Backups"
facts=$("$PYTHON" "$TOOLS_DIR/scripts/install_helpers.py" status --status-dir "$INSTANCE_ROOT/status" 2>/dev/null)
line "last backup" "$("$PYTHON" -c 'import json,sys;f=json.loads(sys.argv[1]);print("unknown (none recorded)" if f.get("age_hours") is None else "%s, %s hours ago, check %s"%(f["backup"],f["age_hours"],f["verification"]))' "$facts")"
line "kept on server" "$(find "$BACKUP_ROOT" -maxdepth 1 -mindepth 1 -type d 2>/dev/null | wc -l) backup(s)"
say ""; say "Disk"
line "data" "$(df -h --output=avail,pcent "$INSTANCE_ROOT" | tail -1 | awk '{print $1" free ("$2" used)"}')"
line "backups" "$(df -h --output=avail,pcent "$BACKUP_ROOT" 2>/dev/null | tail -1 | awk '{print $1" free ("$2" used)"}')"
say ""; say "More: sudo labadda doctor output -> $INSTANCE_ROOT/current/venv/bin/python -m labadda.cli doctor --env-file $ENV_FILE"
