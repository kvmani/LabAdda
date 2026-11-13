#!/usr/bin/env bash
# Take a verified backup now. THE SITE IS CLOSED FOR A FEW MINUTES while it runs.
#   sudo labadda-backup-now [--dry-run] [--copy-to /media/usb/labadda-backups] [--site NAME]
# --copy-to also copies the new backup to that folder and checks the copy (your off-server copy).
set -euo pipefail
SELF="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
# shellcheck source=lib/common.sh
source "$SELF/lib/common.sh"
COPY_TO=""
while (($#)); do
  case $1 in
    --dry-run) DRY_RUN=1 ;; --copy-to) COPY_TO=$2; shift ;; --site) SITE=$2; shift ;;
    -h | --help) sed -n '2,5p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) die "Unknown option $1" ;;
  esac; shift
done
set_paths; need_root
[[ -f $SITE_JSON ]] || die "Site '$SITE' is not installed here."
if ((DRY_RUN)); then
  step "Plan (nothing is changed)"; lifecycle backup --unattended --resume-after-backup; exit 0
fi
step "Backing up (site closed for a few minutes)"
lifecycle backup --unattended --apply --external-writers-stopped --resume-after-backup >/dev/null \
  || die "The backup did not finish. The site may be in maintenance: run labadda-status and read docs/RECOVERY.md."
newest=$(find "$BACKUP_ROOT" -maxdepth 1 -mindepth 1 -type d -printf '%f\n' | sort | tail -1)
ok "backup $newest ($(du -sh "$BACKUP_ROOT/$newest" | cut -f1)) taken and verified; the site is open again"
say "    Manifest digest (note it somewhere safe, it is needed for a restore):"
say "    $(sha256sum "$BACKUP_ROOT/$newest/manifest.json" | cut -d' ' -f1)"
if [[ -n $COPY_TO ]]; then
  step "Copying off the server"
  mkdir -p "$COPY_TO"; cp -a "$BACKUP_ROOT/$newest" "$COPY_TO/"
  [[ $(sha256sum "$COPY_TO/$newest/manifest.json" | cut -d' ' -f1) == $(sha256sum "$BACKUP_ROOT/$newest/manifest.json" | cut -d' ' -f1) ]] \
    || die "The copy does not match. Try another drive."
  ok "copied to $COPY_TO/$newest (backups contain all content: keep the drive locked away)"
fi
