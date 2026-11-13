#!/usr/bin/env bash
# Rehearse the whole intranet rollout from a built offline kit, on this machine, in a scratch folder.
#   sudo scripts/rehearse-rollout.sh KIT_DIR [--upgrade-kit KIT2_DIR] [--keep]
# It runs install.sh (dry run, then for real), status, a second install run (idempotence), a backup with an
# off-server copy, a test restore, an optional upgrade, then removes everything it made. Everything lives
# under LABADDA_ROOT_PREFIX=/srv/rollout-rehearsal-N; the database is labadda_rollout; systemctl is replaced by
# scripts/rollout_fake_systemctl.py inside a private mount namespace; nginx is real, on port 443.
# NOT rehearsed here: real systemd, the real /etc/nginx tree, apt installing missing packages.
set -uo pipefail
export PYTHONDONTWRITEBYTECODE=1
# This machine's own package access stands in for the office mirror (public index allowed for the rehearsal only).
export LABADDA_ALLOW_PUBLIC_INDEX=1
HERE="$(cd "$(dirname "$0")" && pwd)"
KIT="" KIT2="" KEEP=0 OFFLINE=0 ORIGINAL=("$@")
while (($#)); do
  case $1 in --upgrade-kit) KIT2=$2; shift ;; --keep) KEEP=1 ;; --offline-kit) OFFLINE=1 ;; *) KIT=$1 ;; esac; shift
done
[[ -d $KIT && $(id -u) -eq 0 ]] || { sed -n '2,3p' "$0" | sed 's/^# \{0,1\}//'; exit 2; }
if [[ -z ${REHEARSAL_INNER:-} ]]; then
  export REHEARSAL_INNER=1 REHEARSAL_PREFIX="/srv/rollout-rehearsal-$$"
  mkdir -p "$REHEARSAL_PREFIX/state"
  # lifecycle.py clears the environment, so the settings path is written into the stand-in itself.
  printf '#!/bin/sh\nFAKE_SYSTEMCTL_CONFIG=%s exec python3.12 %s "$@"\n' "$REHEARSAL_PREFIX/fake.json" \
    "$HERE/rollout_fake_systemctl.py" >"$REHEARSAL_PREFIX/systemctl"
  chmod +x "$REHEARSAL_PREFIX/systemctl"
  exec unshare -m bash -c "mount --bind '$REHEARSAL_PREFIX/systemctl' /usr/bin/systemctl && exec bash '$0' ${ORIGINAL[*]}"
fi

P="$REHEARSAL_PREFIX"; export LABADDA_ROOT_PREFIX="$P" LABADDA_SITE=rollout FAKE_SYSTEMCTL_CONFIG="$P/fake.json"
export LABADDA_NGINX_MAIN_CONF="$P/etc/nginx/nginx.conf"
FAILS=0
check() { local name=$1; shift; if "$@" >"$P/last.log" 2>&1; then echo "PASS  $name"; else echo "FAIL  $name"; tail -15 "$P/last.log"; FAILS=$((FAILS + 1)); fi; }
mkdir -p "$P/etc/nginx/conf.d" "$P/run" "$P/etc/labadda"
cat >"$P/fake.json" <<JSON
{"state": "$P/state", "unit_dir": "$P/etc/systemd/system", "nginx_conf": "$P/etc/nginx/nginx.conf", "nginx_pid": "$P/run/nginx.pid"}
JSON
cat >"$P/etc/nginx/nginx.conf" <<NGINX
pid $P/run/nginx.pid;
error_log $P/run/nginx-error.log;
events { worker_connections 64; }
http {
  access_log $P/run/nginx-access.log;
  client_body_temp_path $P/run/tmp; proxy_temp_path $P/run/tmp; fastcgi_temp_path $P/run/tmp;
  uwsgi_temp_path $P/run/tmp; scgi_temp_path $P/run/tmp;
  include /etc/nginx/mime.types;
  include $P/etc/nginx/conf.d/*.conf;
}
NGINX
cat >"$P/answers" <<ANS
SITE_TITLE=LabAdda Rehearsal
HOSTNAME_=localhost
TIMEZONE_=Asia/Kolkata
EMAIL_DOMAIN=lab.example.in
FEEDBACK_EMAIL=feedback@lab.example.in
SMTP_RELAY=mail.lab.example.in:25
SMTP_FROM=labadda@lab.example.in
SMTP_STARTTLS=false
SMTP_USER=none
PIP_INDEX_URL=https://pypi.org/simple
PORT=8197
SERVICE_USER=labadda-rh
ADMIN_USER=asha.rollout
ADMIN_NAME=Asha Rollout
ANS

cleanup() {
  ((KEEP)) && { echo "Kept $P (database labadda_rollout, user labadda-rh)"; return; }
  for s in rollout rolloutrestore; do
    bash "$KIT/uninstall-keep-data.sh" --site "$s" --yes >/dev/null 2>&1
  done
  python3.12 "$HERE/rollout_fake_systemctl.py" stop nginx >/dev/null 2>&1
  for u in labadda-rollout.service labadda-rolloutrestore.service; do python3.12 "$HERE/rollout_fake_systemctl.py" stop $u >/dev/null 2>&1; done
  for d in rollout rolloutrestore; do
    runuser -u postgres -- dropdb --if-exists "labadda_$d" >/dev/null 2>&1
    runuser -u postgres -- psql -qc "drop role if exists labadda_$d" >/dev/null 2>&1
  done
  userdel labadda-rh >/dev/null 2>&1; rm -rf "$P"
  echo "Cleaned up the scratch prefix, databases and test account."
}
trap cleanup EXIT

INSTALL=(bash "$KIT/install.sh" --answers "$P/answers" --yes --skip-os-packages)
((OFFLINE)) && INSTALL+=(--offline-kit)
check "install.sh --dry-run runs" "${INSTALL[@]}" --dry-run
check "dry run changed nothing" test ! -e "$P/srv/labadda"
check "kit verifies" python3.12 "$KIT/tools/scripts/kit.py" verify "$KIT"
check "install.sh (real run)" "${INSTALL[@]}"
cp "$P/last.log" "$P/install.log"
check "installed files exist" bash -c "test -L $P/srv/labadda/rollout/current && test -f $P/etc/labadda/rollout.env && test -f $P/etc/labadda/secrets/rollout.db-password && test \$(stat -c %a $P/etc/labadda/rollout.env) = 600"
check "activation token was printed once" grep -q -i "activation\|token" "$P/install.log"
check "HTTPS answers through real nginx" env LABADDA_PROBE_CA_FILE="$P/etc/ssl/labadda/server.crt" python3.12 "$HERE/operations.py" --site "$P/etc/labadda/rollout.site.json" probe
check "status.sh" bash "$KIT/status.sh" --site rollout
cp "$P/last.log" "$P/status.log"; cat "$P/status.log"
check "install.sh again is a no-op" "${INSTALL[@]}"
check "status shows a backup" grep -q "backup" "$P/status.log"
check "backup-now with off-server copy" bash "$KIT/backup-now.sh" --copy-to "$P/usb"
NEWEST=$(ls "$P/srv/labadda-backups/rollout" | sort | tail -1)
DIGEST=$(sha256sum "$P/srv/labadda-backups/rollout/$NEWEST/manifest.json" | cut -d' ' -f1)
check "test restore into a separate copy" bash "$KIT/restore.sh" --bundle "$P/srv/labadda-backups/rollout/$NEWEST" --manifest-sha256 "$DIGEST" --test-site rolloutrestore --port 8198
check "restored copy answers" python3.12 "$HERE/operations.py" --site "$P/etc/labadda/rolloutrestore.site.json" probe --direct
check "restore copy removed again" bash "$KIT/restore.sh" --remove-test --test-site rolloutrestore --site rollout
if [[ -n $KIT2 ]]; then
  UPG=(); ((OFFLINE)) && UPG=(--offline-kit)
  check "upgrade --dry-run" bash "$KIT2/upgrade.sh" --dry-run --site rollout "${UPG[@]}"
  check "upgrade to the second kit" bash "$KIT2/upgrade.sh" --yes --site rollout "${UPG[@]}"
  cp "$P/last.log" "$P/upgrade.log"; tail -12 "$P/upgrade.log"
  check "status after upgrade names the new release" bash -c "bash '$KIT2/status.sh' --site rollout | grep -q \"$(python3.12 -c 'import json,sys;print(json.load(open(sys.argv[1]+"/MANIFEST.json"))["release"])' "$KIT2")\""
fi
check "uninstall-keep-data keeps the data" bash -c "bash '$KIT/uninstall-keep-data.sh' --site rollout --yes && test -d $P/srv/labadda/rollout/releases && test ! -e $P/etc/systemd/system/labadda-rollout.service"
echo; echo "Rehearsal finished with $FAILS failing check(s)."
exit "$FAILS"
