#!/usr/bin/env bash
# Restore a backup into a SEPARATE test copy of the site (own database, folders and port) so you can
# look at it before anything live is touched. For a whole-server recovery use install.sh with
# --restore-bundle on the new server instead (see ROLLOUT-INTRANET.md).
#   sudo bash restore.sh --bundle /srv/labadda-backups/main/<backup> --manifest-sha256 <digest> [--test-site mainrestore] [--port 8101]
#   sudo bash restore.sh --remove-test --test-site mainrestore       drop the test copy again
# Needs the kit of the same or a newer release (run it from the kit folder). Add --dry-run for the plan.
set -euo pipefail
KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "$KIT/lib/common.sh"
MODE_ARGS=() BUNDLE="" DIGEST="" TEST_SITE="" PORT_TEST="8101" REMOVE=0 MAIN_SITE=$SITE
while (($#)); do
  case $1 in
    --bundle) BUNDLE=$2; shift ;; --manifest-sha256) DIGEST=$2; shift ;; --test-site) TEST_SITE=$2; shift ;;
    --port) PORT_TEST=$2; shift ;; --site) MAIN_SITE=$2; shift ;; --remove-test) REMOVE=1 ;; --offline-kit) MODE_ARGS=(--offline-kit) ;; --dry-run) DRY_RUN=1 ;;
    -h | --help) sed -n '2,8p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) die "Unknown option $1" ;;
  esac; shift
done
TEST_SITE=${TEST_SITE:-${MAIN_SITE}restore}
[[ $TEST_SITE != "$MAIN_SITE" ]] || die "The test copy must have a different name from the live site."
SITE=$TEST_SITE; set_paths; need_root
if ((REMOVE)); then
  step "Removing test copy $TEST_SITE"
  [[ -f $SITE_JSON ]] || die "No test copy named $TEST_SITE."
  run "$SYSTEMCTL" disable --now "$UNIT"
  run rm -f "$SYSTEMD_DIR/$UNIT"; run "$SYSTEMCTL" daemon-reload
  run runuser -u postgres -- dropdb --if-exists "labadda_$SITE"
  run runuser -u postgres -- psql -qc "drop role if exists labadda_$SITE"
  run rm -rf "$INSTANCE_ROOT" "$BACKUP_ROOT" "$ETC_DIR/$SITE".* "$SECRETS_DIR/$SITE.db-password"
  ok "test copy removed (the live site was not touched)"; exit 0
fi
[[ -d $BUNDLE && $DIGEST =~ ^[0-9a-f]{64}$ ]] || die "Give --bundle (a backup folder) and --manifest-sha256 (64 hex characters)."
SITE=$MAIN_SITE; set_paths
[[ -f $ANSWERS_FILE ]] || die "No install answers for site $MAIN_SITE; run on the server that holds the live site."
extra=(); ((DRY_RUN)) && extra=(--dry-run)
exec bash "$KIT/install.sh" --site "$TEST_SITE" --answers "$ANSWERS_FILE" --port "$PORT_TEST" --yes --skip-os-packages \
  --no-nginx --no-timer --restore-bundle "$BUNDLE" --manifest-sha256 "$DIGEST" "${MODE_ARGS[@]}" "${extra[@]}"
