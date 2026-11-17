#!/usr/bin/env bash
# Take LabAdda out of service but KEEP all data: services, timer and web site are stopped and removed;
# the database, uploaded files, backups, settings and releases stay where they are.
#   sudo bash uninstall-keep-data.sh [--dry-run] [--yes] [--site NAME]
set -euo pipefail
SELF="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
# shellcheck source=lib/common.sh
source "$SELF/lib/common.sh"
while (($#)); do
  case $1 in --dry-run) DRY_RUN=1 ;; --yes) ASSUME_YES=1 ;; --site) SITE=$2; shift ;; *) die "Unknown option $1" ;; esac; shift
done
set_paths; need_root
step "Taking site '$SITE' out of service (data is kept)"
if ! ((ASSUME_YES || DRY_RUN)); then
  read -r -p "Type the site name ($SITE) to confirm: " reply; [[ $reply == "$SITE" ]] || die "Cancelled."; fi
run "$SYSTEMCTL" disable --now "labadda-backup@$SITE.timer" || true
run "$SYSTEMCTL" disable --now "$UNIT" || true
# A shared site must lose its include line before the file it names, or nginx (and the application
# that owns the site) could no longer reload.
snippet="$NGINX_DIR/snippets/labadda-$SITE.conf"
shared=$(sed -n 's/^SHARED_SITE=//p' "$ANSWERS_FILE" 2>/dev/null || true)
if [[ -f $snippet && -n $shared ]] && ! ((DRY_RUN)); then
  "$PYTHON" "$TOOLS_DIR/scripts/install_helpers.py" attach-site --remove --site-file "$(readlink -f "$PREFIX$shared")" \
    --include "$snippet" >/dev/null || die "Could not remove LabAdda's include line from $shared; nothing else was changed."
fi
run rm -f "$SYSTEMD_DIR/$UNIT" "$NGINX_DIR/conf.d/labadda-$SITE.conf" "$snippet"
run "$SYSTEMCTL" daemon-reload
[[ ! -x $(command -v nginx || echo /nonexistent) ]] || run "$SYSTEMCTL" reload nginx || true
run rm -f "$SBIN_DIR"/labadda-status "$SBIN_DIR"/labadda-backup-now "$SBIN_DIR"/labadda-restore "$SBIN_DIR"/labadda-upgrade "$SBIN_DIR"/labadda-reattach-nginx
ok "stopped and removed the service, timer and web site"
say "    KEPT: $INSTANCE_ROOT  $BACKUP_ROOT  $ETC_DIR  database labadda_$SITE  tools in $TOOLS_DIR"
say "    To bring it back: run install.sh from a kit again; it recognises the kept data."
