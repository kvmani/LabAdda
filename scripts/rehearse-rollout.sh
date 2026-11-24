#!/usr/bin/env bash
# Rehearse the whole intranet rollout from a built offline kit, on this machine, in a scratch folder.
#   sudo scripts/rehearse-rollout.sh KIT_DIR [--upgrade-kit KIT2_DIR] [--keep] [--shared-http | --dedicated-http]
#        [--system-scope]
#   sudo scripts/rehearse-rollout.sh --zip LabAdda-A.zip [--upgrade-zip LabAdda-B.zip] [the options above]
# --zip starts from GitHub's release "Source code (zip)" exactly as on the server: install.sh --zip builds
# the bundle from the zip (no git), then installs it; --upgrade-zip then upgrades with upgrade.sh --zip.
# LabAdda runs as systemd user services of the account labadda-rh (the default, like PM); --system-scope
# rehearses the original system unit instead. --dedicated-http serves http://127.0.0.1/ with no certificate.
# --shared-http installs under http://127.0.0.1/labadda/ inside a stand-in for project_management_software's
# plain-HTTP default site on port 80, and checks that site keeps answering and is restored on uninstall.
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
KIT="" KIT2="" ZIP="" ZIP2="" KEEP=0 OFFLINE=0 SHARED=0 PLAIN=0 SCOPE=user ORIGINAL=("$@")
while (($#)); do
  case $1 in --upgrade-kit) KIT2=$2; shift ;; --zip) ZIP=$(readlink -f "$2"); shift ;; --upgrade-zip) ZIP2=$(readlink -f "$2"); shift ;; --keep) KEEP=1 ;; --offline-kit) OFFLINE=1 ;; --shared-http) SHARED=1 ;; --dedicated-http) PLAIN=1 ;; --system-scope) SCOPE=system ;; *) KIT=$1 ;; esac; shift
done
[[ (-d $KIT || -f $ZIP) && $(id -u) -eq 0 ]] || { sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'; exit 2; }
if [[ -z ${REHEARSAL_INNER:-} ]]; then
  export REHEARSAL_INNER=1 REHEARSAL_PREFIX="/srv/rollout-rehearsal-$$"
  mkdir -p "$REHEARSAL_PREFIX/state"
  # lifecycle.py clears the environment, so the settings path is written into the stand-in itself.
  printf '#!/bin/sh\nFAKE_SYSTEMCTL_CONFIG=%s exec python3.12 %s "$@"\n' "$REHEARSAL_PREFIX/fake.json" \
    "$HERE/rollout_fake_systemctl.py" >"$REHEARSAL_PREFIX/systemctl"
  chmod +x "$REHEARSAL_PREFIX/systemctl"
  exec unshare -m bash -c 'mount --bind "$REHEARSAL_PREFIX/systemctl" /usr/bin/systemctl && exec bash "$@"' \
    labadda-rehearsal "$0" "${ORIGINAL[@]}"
fi

P="$REHEARSAL_PREFIX"; export LABADDA_ROOT_PREFIX="$P" LABADDA_SITE=rollout FAKE_SYSTEMCTL_CONFIG="$P/fake.json"
export LABADDA_NGINX_MAIN_CONF="$P/etc/nginx/nginx.conf"
# No logind here: lingering is a no-op stand-in. The account's units and pid files must be its own.
export LABADDA_LOGINCTL=true
chmod 1777 "$P/state"
# A CA bundle configured for root only (as on some build machines) is unreadable to the service
# account that installs the Python packages; give it a readable copy for this rehearsal.
for var in SSL_CERT_FILE REQUESTS_CA_BUNDLE PIP_CERT; do
  if [[ -n ${!var:-} && -r ${!var} ]]; then
    install -m 0644 "${!var}" "$P/ca-bundle.crt"; export "$var=$P/ca-bundle.crt"
  fi
done
FAILS=0
check() { local name=$1; shift; if "$@" >"$P/last.log" 2>&1; then echo "PASS  $name"; else echo "FAIL  $name"; tail -15 "$P/last.log"; FAILS=$((FAILS + 1)); fi; }
mkdir -p "$P/etc/nginx/conf.d" "$P/run" "$P/etc/labadda"
cat >"$P/fake.json" <<JSON
{"state": "$P/state", "unit_dir": "$P/etc/systemd/system", "user_unit_dir": "$P/home/labadda-rh/.config/systemd/user",
 "nginx_conf": "$P/etc/nginx/nginx.conf", "nginx_pid": "$P/run/nginx.pid"}
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
  include $P/etc/nginx/sites-enabled/*;
}
NGINX
mkdir -p "$P/etc/nginx/sites-available" "$P/etc/nginx/sites-enabled"
if ((SHARED)); then
  # project_management_software's real site file (docs/deployment/pm-coexistence.md), enabled by
  # symlink as on the server, with a stand-in for PM's production backend on its port 8000.
  cp "$HERE/../docs/deployment/pm-reference/apex_pm.active.conf" "$P/etc/nginx/sites-available/apex_pm"
  python3.12 -I -c 'import http.server as h
class R(h.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"pm production backend " + self.path.encode())
    def log_message(self, *a): pass
h.HTTPServer(("127.0.0.1", 8000), R).serve_forever()' &
  PM_BACKEND=$!
  ln -s "$P/etc/nginx/sites-available/apex_pm" "$P/etc/nginx/sites-enabled/apex_pm"
  cp -p "$P/etc/nginx/sites-available/apex_pm" "$P/pm-site.original"
fi
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
# A bundle older than service scopes (0.0.2) rejects the answer and always installs system scope.
if [[ -n $ZIP || -f $KIT/lib/source.sh ]]; then printf 'SERVICE_SCOPE=%s\n' "$SCOPE" >>"$P/answers"; else SCOPE=system; fi
if ((PLAIN)); then
  sed -i 's/^HOSTNAME_=localhost$/HOSTNAME_=127.0.0.1/' "$P/answers"
  printf 'WEB_ACCESS=dedicated-http\n' >>"$P/answers"
fi
if ((SHARED)); then
  sed -i 's/^HOSTNAME_=localhost$/HOSTNAME_=127.0.0.1/' "$P/answers"
  printf 'WEB_ACCESS=shared-http\nURL_PATH=/labadda\nSHARED_SITE=/etc/nginx/sites-enabled/apex_pm\n' >>"$P/answers"
fi

cleanup() {
  [[ -z ${PM_BACKEND:-} ]] || kill "$PM_BACKEND" 2>/dev/null
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

# The page names its scripts relative to <base href="/labadda/">; fetch one through nginx's alias.
shell_under_prefix() {
  local page asset
  page=$(curl -sf --noproxy '*' http://127.0.0.1/labadda/) || return 1
  grep -q '<base href="/labadda/">' <<<"$page" || return 1
  asset=$(grep -o 'assets/[A-Za-z0-9._-]*\.js' <<<"$page" | head -1)
  [[ -n $asset ]] && curl -sf --noproxy '*' -o /dev/null "http://127.0.0.1/labadda/$asset"
}

unpack_zip() { python3.12 -I "$HERE/source_zip.py" extract "$1" "$2"; }
if [[ -n $ZIP ]]; then
  export LABADDA_BUILD_ROOT="$P/builds"
  SOURCE=$(unpack_zip "$ZIP" "$P/source") || { echo "FAIL  the zip unpacks"; exit 1; }
  INSTALL=(bash "$SOURCE/deploy/install.sh" --zip "$ZIP" --sha256 "$(sha256sum "$ZIP" | cut -d' ' -f1)"
    --answers "$P/answers" --yes --skip-os-packages)
  check "a zip with the wrong hash is refused" bash -c "! bash '$SOURCE/deploy/install.sh' --zip '$ZIP' --sha256 $(printf '0%.0s' {1..64}) --answers '$P/answers' --yes --dry-run"
else
  INSTALL=(bash "$KIT/install.sh" --answers "$P/answers" --yes --skip-os-packages)
fi
((OFFLINE)) && INSTALL+=(--offline-kit)
check "install.sh --dry-run runs" "${INSTALL[@]}" --dry-run
check "dry run changed nothing" test ! -e "$P/srv/labadda"
[[ -n $ZIP ]] || check "kit verifies" python3.12 "$KIT/tools/scripts/kit.py" verify "$KIT"
check "install.sh (real run)" "${INSTALL[@]}"
cp "$P/last.log" "$P/install.log"
if [[ -n $ZIP ]]; then
  KIT=$(find "$P/builds" -mindepth 3 -maxdepth 3 -type d -name 'labadda-*-bundle' | head -1)
  check "the bundle built from the zip verifies" python3.12 "$KIT/tools/scripts/kit.py" verify "$KIT"
  check "the build names the zip's commit" bash -c "grep -q \"\$(python3.12 -I '$HERE/source_zip.py' identity '$ZIP' | cut -d' ' -f1)\" '$KIT/MANIFEST.json'"
fi
check "installed files exist" bash -c "test -L $P/srv/labadda/rollout/current && test -f $P/etc/labadda/rollout.env && test -f $P/etc/labadda/secrets/rollout.db-password && test \$(stat -c %a $P/etc/labadda/rollout.env) = 600"
if [[ $SCOPE == user ]]; then
  check "user-scope units in the account's own folder, instance owned by it" bash -c "test -f $P/home/labadda-rh/.config/systemd/user/labadda-rollout.service && test -f $P/home/labadda-rh/.config/systemd/user/labadda-backup@.timer && test ! -e $P/etc/systemd/system/labadda-rollout.service && test \$(stat -c %U $P/srv/labadda/rollout/current/) = labadda-rh && test \$(stat -c %U $P/srv/labadda-backups/rollout) = labadda-rh"
fi
check "activation token was printed once" grep -q -i "activation\|token" "$P/install.log"
if ((SHARED)); then
  check "http://127.0.0.1/labadda/ answers through real nginx" python3.12 "$HERE/operations.py" --site "$P/etc/labadda/rollout.site.json" probe
  check "sign-in page and its script load under /labadda/" shell_under_prefix
  check "PM's own API route still reaches PM's backend" bash -c "curl -sf --noproxy '*' http://127.0.0.1/production/api/v1/health | grep -qx 'pm production backend /api/v1/health'"
  check "the shared site gained exactly one include line" bash -c "diff '$P/pm-site.original' '$P/etc/nginx/sites-available/apex_pm' | grep -c '^>' | grep -qx 1"
  check "the shared site is still a symlink" test -L "$P/etc/nginx/sites-enabled/apex_pm"
elif ((PLAIN)); then
  check "http://127.0.0.1/ answers through real nginx" python3.12 "$HERE/operations.py" --site "$P/etc/labadda/rollout.site.json" probe
else
  check "HTTPS answers through real nginx" env LABADDA_PROBE_CA_FILE="$P/etc/ssl/labadda/server.crt" python3.12 "$HERE/operations.py" --site "$P/etc/labadda/rollout.site.json" probe
fi
check "status.sh" bash "$KIT/status.sh" --site rollout
cp "$P/last.log" "$P/status.log"; cat "$P/status.log"
check "status --json is valid JSON naming the site" bash -c "bash '$KIT/status.sh' --site rollout --json | python3.12 -c 'import json,sys;assert json.load(sys.stdin)[\"site\"]==\"rollout\"'"
check "15-minute health check timer installed" bash -c "ls '$P'/home/labadda-rh/.config/systemd/user/labadda-check@.timer '$P'/etc/systemd/system/labadda-check@.timer 2>/dev/null | grep -q check"
check "labadda-admin check reports healthy" bash "$KIT/admin.sh" check --site rollout
check "labadda-admin lists backups" bash "$KIT/admin.sh" backups --site rollout
check "labadda-admin support report" bash "$KIT/admin.sh" support-report "$P" --site rollout
check "install.sh again is a no-op" "${INSTALL[@]}"
check "status shows a backup" grep -q "backup" "$P/status.log"
check "backup-now with off-server copy" bash "$KIT/backup-now.sh" --copy-to "$P/usb"
NEWEST=$(ls "$P/srv/labadda-backups/rollout" | sort | tail -1)
DIGEST=$(sha256sum "$P/srv/labadda-backups/rollout/$NEWEST/manifest.json" | cut -d' ' -f1)
check "test restore into a separate copy" bash "$KIT/restore.sh" --bundle "$P/srv/labadda-backups/rollout/$NEWEST" --manifest-sha256 "$DIGEST" --test-site rolloutrestore --port 8198
check "restored copy answers" python3.12 "$HERE/operations.py" --site "$P/etc/labadda/rolloutrestore.site.json" probe --direct
check "restore copy removed again" bash "$KIT/restore.sh" --remove-test --test-site rolloutrestore --site rollout
if [[ -n $ZIP2 ]]; then
  SOURCE2=$(unpack_zip "$ZIP2" "$P/source2")
  NEW=$(sed -n 's/^__version__ = "\(.*\)"/\1/p' "$SOURCE2/backend/labadda/__init__.py")
  UPZ=(bash "$SOURCE2/deploy/upgrade.sh" --zip "$ZIP2" --sha256 "$(sha256sum "$ZIP2" | cut -d' ' -f1)" --site rollout)
  check "upgrade from the zip --dry-run (sanity checks only)" "${UPZ[@]}" --dry-run
  check "upgrade from the zip" "${UPZ[@]}" --yes
  cp "$P/last.log" "$P/upgrade.log"; tail -12 "$P/upgrade.log"
  check "status after upgrade names $NEW" bash -c "bash '$KIT/status.sh' --site rollout | grep -q '$NEW'"
  check "upgraded site answers" python3.12 "$HERE/operations.py" --site "$P/etc/labadda/rollout.site.json" probe --direct
fi
if [[ -n $KIT2 ]]; then
  UPG=(); ((OFFLINE)) && UPG=(--offline-kit)
  check "upgrade --dry-run" bash "$KIT2/upgrade.sh" --dry-run --site rollout "${UPG[@]}"
  check "upgrade to the second kit" bash "$KIT2/upgrade.sh" --yes --site rollout "${UPG[@]}"
  cp "$P/last.log" "$P/upgrade.log"; tail -12 "$P/upgrade.log"
  check "status after upgrade names the new release" bash -c "bash '$KIT2/status.sh' --site rollout | grep -q \"$(python3.12 -c 'import json,sys;print(json.load(open(sys.argv[1]+"/MANIFEST.json"))["release"])' "$KIT2")\""
fi
if ((SHARED)); then
  # The owning application rewrites its site (as deploy_all does); reattach must restore LabAdda only.
  cp -p "$P/pm-site.original" "$P/etc/nginx/sites-available/apex_pm"
  check "reattach after the shared site was rewritten" bash "$KIT/reattach-nginx.sh" --site rollout
fi
check "uninstall-keep-data keeps the data" bash -c "bash '$KIT/uninstall-keep-data.sh' --site rollout --yes && test -d $P/srv/labadda/rollout/releases && test ! -e $P/etc/systemd/system/labadda-rollout.service && test ! -e $P/home/labadda-rh/.config/systemd/user/labadda-rollout.service"
if ((SHARED)); then
  check "uninstall restores the shared site byte for byte" cmp "$P/pm-site.original" "$P/etc/nginx/sites-available/apex_pm"
  check "nginx still accepts the configuration" nginx -t -c "$P/etc/nginx/nginx.conf"
fi
echo; echo "Rehearsal finished with $FAILS failing check(s)."
exit "$FAILS"
