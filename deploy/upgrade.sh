#!/usr/bin/env bash
# Upgrade to a new release: sanity checks, backup first, verify, migrate, restart, check health.
# From GitHub's release zip (no git, packages from the office mirrors), as for project_management_software:
#   unzip LabAdda-X.Y.Z.zip && sudo bash LabAdda-X.Y.Z/deploy/upgrade.sh --zip LabAdda-X.Y.Z.zip --sha256 HEX [--dry-run]
# From an already built bundle:
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
# shellcheck source=lib/source.sh
source "$KIT/lib/source.sh"
ORIGINAL=("$@") ZIP="" ZIP_SHA=""
while (($#)); do
  case $1 in
    --dry-run) DRY_RUN=1 ;; --yes) ASSUME_YES=1 ;; --site) SITE=$2; shift ;;
    --zip) ZIP=$(readlink -f "$2"); shift ;; --sha256) ZIP_SHA=$2; shift ;;
    --offline-kit) MODE=offline ;; --pip-index-url) PIP_INDEX_URL=$2; shift ;; --pip-trusted-host) PIP_TRUSTED_HOST=$2; shift ;;
    -h | --help) sed -n '2,10p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) die "Unknown option $1" ;;
  esac; shift
done
set_paths; need_root
[[ -f $SITE_JSON ]] || die "Site '$SITE' is not installed here. Use install.sh for a first install."
load_site_identity
[[ ! -f $ANSWERS_FILE ]] || load_answers "$ANSWERS_FILE"  # keeps the mirror address chosen at install
if [[ -n $ZIP ]]; then SELF_ROOT="$KIT/.."; from_source_zip upgrade "${ORIGINAL[@]}"; fi
preflight_upgrade
step "Checking the new kit"
verify_kit "$KIT"
check_mode "$KIT"
VERSION=$(kit_field "$KIT" release)
CURRENT=$(current_version)
[[ $CURRENT != none ]] || die "No active release found; run install.sh."
if [[ $VERSION == "$CURRENT" ]]; then
  assert_release_identity "$INSTANCE_ROOT/current/manifest.json" "$KIT/MANIFEST.json"
  ok "identical release $VERSION is already running; nothing to do."; exit 0
fi
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
# The backend operation lock serializes upgrades with scheduled backups. Keeping the timer
# configured as-is also preserves an intentionally timer-free installation or restore target.
step "Upgrading (site closed)"
if lifecycle upgrade --apply --recover-compatible --external-writers-stopped --expected-current "$CURRENT" --expected-schema "$OLD_SCHEMA" \
  --candidate "$VERSION" >/dev/null; then
  ok "now running $VERSION; the site is open again"
  install_check_timer
  ( cd "$INSTANCE_ROOT/current/backend" && as_service "$INSTANCE_ROOT/current/venv/bin/python" -m labadda.cli doctor --env-file "$ENV_FILE" ) || warn "the doctor reported problems above"
  exit 0
fi
warn "Upgrade did not complete. Run labadda-status and inspect its operation journal in $INSTANCE_ROOT/operations."
say "    Use only the bundle and manifest digest in this upgrade's backup_verified record."
say "    If that record is absent, a backup for this upgrade was not confirmed."
exit 1
