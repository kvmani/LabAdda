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
load_site_identity
if ((DRY_RUN)); then
  step "Plan (nothing is changed)"; lifecycle backup --unattended --resume-after-backup; exit 0
fi
step "Backing up (site closed for a few minutes)"
receipt=$(lifecycle backup --unattended --apply --external-writers-stopped --resume-after-backup) \
  || die "The backup did not finish. The site may be in maintenance: run labadda-status and read docs/RECOVERY.md."
bundle=$("$PYTHON" -c 'import json,sys;print(json.load(sys.stdin)["backup"])' <<<"$receipt")
digest=$("$PYTHON" -c 'import json,sys;print(json.load(sys.stdin)["manifest_sha256"])' <<<"$receipt")
[[ ${bundle%/*} == "$BACKUP_ROOT" && -d $bundle && $digest =~ ^[0-9a-f]{64}$ ]] \
  || die "Unconfirmed backup receipt; inspect the local operation journal."
newest=${bundle##*/}
ok "backup $newest ($(du -sh "$bundle" | cut -f1)) taken and verified; the site is open again"
say "    Manifest digest (note it somewhere safe, it is needed for a restore):"
say "    $digest"
if [[ -n $COPY_TO ]]; then
  step "Copying off the server"
  mkdir -p "$COPY_TO"
  [[ ! -e $COPY_TO/$newest && ! -L $COPY_TO/$newest ]] || die "Destination backup name already exists."
  cp -a "$bundle" "$COPY_TO/"
  is_user_scope && chown -R "$SERVICE_USER:$SERVICE_USER" "$COPY_TO/$newest"
  with_env "$INSTANCE_ROOT/current/venv/bin/python" -m labadda.cli verify-backup "$COPY_TO/$newest" \
    --manifest-sha256 "$digest" >/dev/null || die "Copied backup failed full verification. Keep the original and recopy."
  ok "copied to $COPY_TO/$newest (backups contain all content: keep the drive locked away)"
fi
