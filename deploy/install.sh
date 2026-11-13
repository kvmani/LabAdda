#!/usr/bin/env bash
# Install LabAdda on Ubuntu 24.04 from the release bundle. Run as root, from the bundle folder.
# Default (mirror mode): operating system packages come from this server's apt sources and Python packages
# (exact pins) from the office Python mirror. With --offline-kit they come from the kit instead.
#   sudo bash install.sh                  asks a few questions, then does everything
#   sudo bash install.sh --dry-run        shows the plan; changes nothing
# Options: --pip-index-url URL [--pip-trusted-host HOST]  --offline-kit  --answers FILE  --yes  --cert FILE --key FILE [--ca-file CA.crt]  --site NAME  --port N  --service-user NAME
#          --skip-os-packages  --no-nginx  --no-timer  --restore-bundle DIR --manifest-sha256 HEX
# Safe to run again: finished steps are recognised and skipped. Rehearsal: LABADDA_ROOT_PREFIX=DIR.
set -euo pipefail
KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "$KIT/lib/common.sh"
# shellcheck source=lib/steps.sh
source "$KIT/lib/steps.sh"

SMTP_FROM="" SMTP_STARTTLS="" SMTP_USER="" SITE_TITLE="" HOSTNAME_="" TIMEZONE_="" EMAIL_DOMAIN="" FEEDBACK_EMAIL="" SMTP_RELAY="" PORT="" SERVICE_USER=""
ADMIN_USER="" ADMIN_NAME="" CERT_FILE="" KEY_FILE="" RESTORE_BUNDLE="" RESTORE_SHA=""
CA_FILE="" ANSWERS="" NO_NGINX=0 NO_TIMER=0 SKIP_OS_PACKAGES=0 EXPECT_FINGERPRINT=""

while (($#)); do
  case $1 in
    --dry-run) DRY_RUN=1 ;;
    --yes) ASSUME_YES=1 ;;
    --answers) ANSWERS=$2; shift ;;
    --cert) CERT_FILE=$2; shift ;;
    --key) KEY_FILE=$2; shift ;;
    --ca-file) CA_FILE=$2; shift ;;
    --offline-kit) MODE=offline ;;
    --pip-index-url) PIP_INDEX_URL=$2; shift ;;
    --pip-trusted-host) PIP_TRUSTED_HOST=$2; shift ;;
    --site) SITE=$2; shift ;;
    --port) PORT=$2; shift ;;
    --service-user) SERVICE_USER=$2; shift ;;
    --kit-fingerprint) EXPECT_FINGERPRINT=$2; shift ;;
    --restore-bundle) RESTORE_BUNDLE=$2; shift ;;
    --manifest-sha256) RESTORE_SHA=$2; shift ;;
    --skip-os-packages) SKIP_OS_PACKAGES=1 ;;
    --no-nginx) NO_NGINX=1 ;;
    --no-timer) NO_TIMER=1 ;;
    -h | --help) sed -n '2,11p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) die "Unknown option $1 (see --help)" ;;
  esac
  shift
done

set_paths
[[ -z $ANSWERS ]] || load_answers "$ANSWERS"
[[ ! -f $ANSWERS_FILE ]] || load_answers "$ANSWERS_FILE"  # a re-run reuses the earlier answers
[[ -z $CERT_FILE ]] || [[ -n $KEY_FILE ]] || die "--cert needs --key as well."

step "Checking this machine"
need_root
if [[ -z $PREFIX ]]; then
  . /etc/os-release
  [[ ${ID:-} == ubuntu && ${VERSION_ID:-} == 24.04 ]] || die "This kit is for Ubuntu 24.04 only (found ${PRETTY_NAME:-unknown})."
fi
command -v "$PYTHON" >/dev/null || die "python3.12 is missing. It ships with Ubuntu 24.04; check this is the right server."
free_gb=$(df -Pk "${PREFIX:-/}" | awk 'NR==2{print int($4/1048576)}')
((free_gb >= 3)) || die "Only ${free_gb} GB free; at least 3 GB are needed for the install, more for data and backups."
ok "Ubuntu 24.04, python3.12, ${free_gb} GB free"

step "Checking the kit"
verify_kit "$KIT"
fingerprint=$(sha256sum "$KIT/SHA256SUMS" | cut -d' ' -f1)
say "    Kit fingerprint: $fingerprint"
if [[ -n $EXPECT_FINGERPRINT && $EXPECT_FINGERPRINT != "$fingerprint" ]]; then
  die "The fingerprint does not match the one noted when the kit was built. Do not install this kit."; fi
check_mode "$KIT"
VERSION=$(kit_field "$KIT" release)
say "    Release: $VERSION"

step "Questions about this site"
ask SITE_TITLE "Site name shown to staff" "LabAdda"
ask HOSTNAME_ "Server hostname people type in the browser (for example labadda.lab.example.in)" ""
ask TIMEZONE_ "Time zone" "Asia/Kolkata"
ask EMAIL_DOMAIN "E-mail domain of staff addresses (the part after @)" ""
ask FEEDBACK_EMAIL "Administrator e-mail that receives feedback (type none to skip)" "none"
ask SMTP_RELAY "Mail relay host:port (type none to skip)" "none"
if [[ $FEEDBACK_EMAIL != none && $SMTP_RELAY != none ]]; then
  ask SMTP_FROM "Address feedback mail is sent from" "labadda@$HOSTNAME_"
  ask SMTP_STARTTLS "Does the relay use STARTTLS (true/false)" "false"
  ask SMTP_USER "Relay user name (type none if the relay needs no login)" "none"
fi
ask PORT "Private port for the app on this server" "8100"
ask SERVICE_USER "Service account name" "labadda"
"$PYTHON" "$KIT/tools/scripts/install_helpers.py" site-json --site "$SITE" --prefix "$PREFIX" --hostname "$HOSTNAME_" \
  --port "$PORT" --user "$SERVICE_USER" >/dev/null || die "One of the answers cannot be used (see above)."
"$PYTHON" -c 'import sys;sys.path.insert(0,sys.argv[1]);import install_helpers as h;h.check_answers(*sys.argv[2:])' \
  "$KIT/tools/scripts" "$SITE" "$HOSTNAME_" "$TIMEZONE_" "$EMAIL_DOMAIN" "$(blank_if_none "$FEEDBACK_EMAIL")" \
  || die "One of the answers cannot be used (see above)."
[[ -f /usr/share/zoneinfo/$TIMEZONE_ ]] || [[ -n $PREFIX ]] || die "Unknown time zone $TIMEZONE_."

step_os_packages
step_service_user
step_tools
step_database
step_config
step_release
step_tls
step_render_units
step_initialize
step_admin
step_start
step_backup_and_doctor

step "Finished"
if ((DRY_RUN)); then say "    Dry run only: nothing was changed."; else
  say "    Open https://$HOSTNAME_/ and sign in with the administrator account."
  say "    Daily check: sudo labadda-status      Manual backup: sudo labadda-backup-now"
fi
