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
[[ $MAIN_SITE =~ ^[a-z][a-z0-9]{0,19}$ ]] || die "Invalid source site name."
[[ $TEST_SITE != "$MAIN_SITE" ]] || die "The test copy must have a different name from the live site."
SITE=$TEST_SITE; set_paths; need_root
marker="$INSTANCE_ROOT/restore-test-source"
if ((REMOVE)); then
  step "Removing test copy $TEST_SITE"
  [[ -f $SITE_JSON ]] || die "No test copy named $TEST_SITE."
  [[ -f $marker && ! -L $marker && $(<"$marker") == "$MAIN_SITE:$TEST_SITE:$INSTANCE_ROOT" ]] \
    || die "Refusing removal: this site has no matching disposable restore-test provenance."
  [[ $(site_field root) == "$INSTANCE_ROOT" ]] || die "Restore-test instance path does not match."
  load_site_identity
  run svc disable --now "$UNIT"
  run rm -f "$SYSTEMD_DIR/$UNIT"; run svc daemon-reload
  run runuser -u postgres -- dropdb --if-exists "labadda_$SITE"
  run runuser -u postgres -- psql -qc "drop role if exists labadda_$SITE"
  run rm -rf "$INSTANCE_ROOT" "$BACKUP_ROOT" "$ETC_DIR/$SITE".* "$SECRETS_DIR/$SITE.db-password"
  ok "test copy removed (the live site was not touched)"; exit 0
fi
[[ ! -e $SITE_JSON && ! -e $INSTANCE_ROOT ]] || die "Restore-test target already exists; choose a new disposable name."
[[ -d $BUNDLE && $DIGEST =~ ^[0-9a-f]{64}$ ]] || die "Give --bundle (a backup folder) and --manifest-sha256 (64 hex characters)."
SITE=$MAIN_SITE; set_paths
[[ -f $ANSWERS_FILE ]] || die "No install answers for site $MAIN_SITE; run on the server that holds the live site."
# A disposable copy must not process copied mail, reminders or scheduled personnel changes.
isolated_answers=$(mktemp)
trap 'rm -f "$isolated_answers"' EXIT
# A system-scope copy gets its own account. A user-scope copy runs under the live site's account (like
# a second PM instance), isolated by its own instance folder, database, port, cookie and settings.
# Scope from the live site's description, else from its answers (a rebuilt server), else system.
if [[ -f $SITE_JSON ]]; then load_site_identity
else SERVICE_SCOPE=$(sed -n 's/^SERVICE_SCOPE=//p' "$ANSWERS_FILE"); SERVICE_SCOPE=${SERVICE_SCOPE:-system}; fi
account_override=(-e '/^SERVICE_USER=/d')
is_user_scope && account_override=()
sed -e '/^FEEDBACK_EMAIL=/d' -e '/^SMTP_RELAY=/d' -e '/^SMTP_USER=/d' \
  -e '/^RUN_SCHEDULER=/d' "${account_override[@]}" "$ANSWERS_FILE" >"$isolated_answers"
printf 'FEEDBACK_EMAIL=none\nSMTP_RELAY=none\nSMTP_USER=none\nRUN_SCHEDULER=false\n' >>"$isolated_answers"
is_user_scope || printf 'SERVICE_USER=labadda-%s\n' "$TEST_SITE" >>"$isolated_answers"
extra=(); ((DRY_RUN)) && extra=(--dry-run)
bash "$KIT/install.sh" --site "$TEST_SITE" --answers "$isolated_answers" --port "$PORT_TEST" --yes --skip-os-packages \
  --no-nginx --no-timer --restore-bundle "$BUNDLE" --manifest-sha256 "$DIGEST" "${MODE_ARGS[@]}" "${extra[@]}"

if ! ((DRY_RUN)); then
  SITE=$TEST_SITE; set_paths
  printf '%s\n' "$MAIN_SITE:$TEST_SITE:$INSTANCE_ROOT" | write_file 0600 root:root "$INSTANCE_ROOT/restore-test-source"
fi
