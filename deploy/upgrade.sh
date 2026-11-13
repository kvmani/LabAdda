#!/usr/bin/env bash
# Upgrade to the release in a NEW offline kit: backup first, verify, migrate, restart, check health.
#   cd /media/usb/labadda-<new-version>-bundle && sudo bash upgrade.sh [--dry-run] [--yes] [--offline-kit]
# The site is closed to users while this runs. If something fails the script puts the old version
# back automatically when the database allows it; otherwise it leaves the site closed and says
# exactly what to do. Your data is never rewound silently.
set -euo pipefail
KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "$KIT/lib/common.sh"
# shellcheck source=lib/steps.sh
source "$KIT/lib/steps.sh"
while (($#)); do
  case $1 in
    --dry-run) DRY_RUN=1 ;; --yes) ASSUME_YES=1 ;; --site) SITE=$2; shift ;;
    --offline-kit) MODE=offline ;; --pip-index-url) PIP_INDEX_URL=$2; shift ;; --pip-trusted-host) PIP_TRUSTED_HOST=$2; shift ;;
    -h | --help) sed -n '2,6p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) die "Unknown option $1" ;;
  esac; shift
done
set_paths; need_root
[[ -f $SITE_JSON ]] || die "Site '$SITE' is not installed here. Use install.sh for a first install."
SERVICE_USER=$(site_field user)
[[ ! -f $ANSWERS_FILE ]] || load_answers "$ANSWERS_FILE"  # keeps the mirror address chosen at install
step "Checking the new kit"
verify_kit "$KIT"
check_mode "$KIT"
VERSION=$(kit_field "$KIT" release)
CURRENT=$(current_version)
[[ $CURRENT != none ]] || die "No active release found; run install.sh."
if [[ $VERSION == "$CURRENT" ]]; then ok "release $VERSION is already running; nothing to do."; exit 0; fi
say "    Running now: $CURRENT   New: $VERSION"

step_tools
step_release
manifest_schema() { "$PYTHON" -c 'import json,sys;print(json.load(open(sys.argv[1]))["schema"])' "$INSTANCE_ROOT/releases/$1/manifest.json"; }
if ((DRY_RUN)); then
  say "    [dry-run] the new release is not installed in a dry run; showing the plan needs it."
  say "    Plan: close site, stop service, backup and verify, migrate, switch to $VERSION, start, check health, reopen."
  exit 0
fi
OLD_SCHEMA=$(schema_of "$CURRENT"); NEW_SCHEMA=$(manifest_schema "$VERSION")
say "    Database schema now $OLD_SCHEMA; new release expects $NEW_SCHEMA"
step "Plan"
lifecycle upgrade --expected-current "$CURRENT" --expected-schema "$OLD_SCHEMA" --candidate "$VERSION"
if ! ((ASSUME_YES)); then
  read -r -p "Close the site and upgrade now? Type UPGRADE to continue: " reply
  [[ $reply == UPGRADE ]] || die "Cancelled. Nothing was changed except installing the new files beside the old."
fi
"$SYSTEMCTL" stop "labadda-backup@$SITE.timer" 2>/dev/null || true
step "Upgrading (site closed)"
if lifecycle upgrade --apply --external-writers-stopped --expected-current "$CURRENT" --expected-schema "$OLD_SCHEMA" \
  --candidate "$VERSION" >/dev/null; then
  "$SYSTEMCTL" start "labadda-backup@$SITE.timer" 2>/dev/null || true
  ok "now running $VERSION; the site is open again"
  ( cd "$INSTANCE_ROOT/current/backend" && "$INSTANCE_ROOT/current/venv/bin/python" -m labadda.cli doctor --env-file "$ENV_FILE" ) || warn "the doctor reported problems above"
  exit 0
fi

step "The upgrade did not finish - checking whether the old version can be put back"
NOW=$(current_version); OBSERVED=$(schema_of "$NOW" || true)
reopen() { "$SYSTEMCTL" start "$UNIT"; wait_for_health 90 && rm -f "$INSTANCE_ROOT/traffic/maintenance"; }
if [[ $NOW == "$CURRENT" && $OBSERVED == "$OLD_SCHEMA" ]]; then
  reopen && { ok "ROLLED BACK AUTOMATICALLY: nothing had changed; $CURRENT is running and the site is open."; exit 1; }
elif [[ $NOW == "$VERSION" && $OLD_SCHEMA == "$NEW_SCHEMA" && $OBSERVED == "$OLD_SCHEMA" ]]; then
  with_env release_tool rollback --instance "$INSTANCE_ROOT" --release "$CURRENT" --database-schema "$OBSERVED" \
    --writers-quiesced --backup-verified >/dev/null && reopen \
    && { ok "ROLLED BACK AUTOMATICALLY to $CURRENT (same database layout); the site is open."; exit 1; }
fi
newest=$(find "$BACKUP_ROOT" -maxdepth 1 -mindepth 1 -type d -printf '%f\n' | sort | tail -1)
warn "NOT rolled back automatically. The SITE IS LEFT CLOSED so no data is lost."
say "    The backup taken just before the upgrade is: $BACKUP_ROOT/$newest"
say "    1. Run: sudo labadda-status   and keep the output."
say "    2. Run: labadda doctor (see ROLLOUT-INTRANET.md, 'If an upgrade fails') and send both outputs."
say "    3. To go back to $CURRENT, restore that backup: sudo bash restore.sh --help (ROLLOUT-INTRANET.md, 'Rollback')."
exit 1
