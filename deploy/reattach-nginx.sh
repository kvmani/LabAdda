#!/usr/bin/env bash
# Put LabAdda back into the shared nginx site after the application that owns it rewrote its site file
# (for example project_management_software's deploy_all). Changes only LabAdda's own include line.
#   sudo labadda-reattach-nginx [--site NAME] [--dry-run]
set -euo pipefail
SELF="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
# shellcheck source=lib/common.sh
source "$SELF/lib/common.sh"
# shellcheck source=lib/steps.sh
source "$SELF/lib/steps.sh"
while (($#)); do case $1 in --site) SITE=$2; shift ;; --dry-run) DRY_RUN=1 ;; *) die "Unknown option $1" ;; esac; shift; done
set_paths; need_root
[[ -f $ANSWERS_FILE ]] || die "Site '$SITE' is not installed here (no $ANSWERS_FILE)."
load_answers "$ANSWERS_FILE"
is_shared_http || die "Site '$SITE' has its own nginx server block; there is nothing to reattach."
step "Adding LabAdda back to $SHARED_SITE"
if ((DRY_RUN)); then say "    [dry-run] would add one include line to $SHARED_SITE and reload nginx"; exit 0; fi
out=$(mktemp -d)/review
operations render --out "$out" >/dev/null
attach_shared_site "$out"
"$SYSTEMCTL" reload nginx
operations probe >/dev/null && ok "$(site_url) answers" || die "nginx reloaded but $(site_url) does not answer; run labadda-status."
