# Install steps shared by install.sh and restore.sh. Sourced after common.sh.
# Each step checks what is already done first, so running the installer again is safe.

REQUIRED_DEBS=(postgresql-16 postgresql-client-16 nginx python3.12-venv openssl)

step_os_packages() {
  step "Operating system packages (from the kit, no internet)"
  local missing=() p work
  for p in "${REQUIRED_DEBS[@]}"; do
    dpkg-query -W -f='${Status}' "$p" 2>/dev/null | grep -q "install ok installed" || missing+=("$p")
  done
  if ((${#missing[@]} == 0)); then ok "already installed: ${REQUIRED_DEBS[*]}"; return 0; fi
  [[ -f $KIT/os-packages/Packages.gz ]] || die "The kit has no os-packages folder; rebuild the kit with make-offline-kit.sh."
  work=$(mktemp -d)
  mkdir -p "$work/lists/partial" "$work/cache/archives/partial"
  printf 'deb [trusted=yes] file:%s ./\n' "$KIT/os-packages" >"$work/kit.list"
  local apt=(apt-get -o "Dir::Etc::SourceList=$work/kit.list" -o Dir::Etc::SourceParts=/dev/null
    -o "Dir::State::Lists=$work/lists" -o "Dir::Cache=$work/cache" -o Acquire::Languages=none
    -o Acquire::AllowInsecureRepositories=true -o APT::Get::AllowUnauthenticated=true)
  say "    needed: ${missing[*]}"
  "${apt[@]}" -qq update >/dev/null 2>&1 || die "Could not read the kit's package list (os-packages/Packages.gz)."
  "${apt[@]}" -s -y --no-install-recommends install "${missing[@]}" >"$work/plan.txt" 2>&1 \
    || { cat "$work/plan.txt" >&2; die "The kit cannot satisfy the packages above. Rebuild it on Ubuntu 24.04 with make-offline-kit.sh."; }
  ok "the kit can install: $(grep -c '^Inst ' "$work/plan.txt") package(s)"
  if ((DRY_RUN)); then rm -rf "$work"; return 0; fi
  [[ ${SKIP_OS_PACKAGES:-0} -eq 1 ]] && { warn "skipping the install on request"; rm -rf "$work"; return 0; }
  DEBIAN_FRONTEND=noninteractive "${apt[@]}" -y --no-install-recommends install "${missing[@]}" >/dev/null
  rm -rf "$work"
  ok "installed: ${missing[*]}"
}

step_service_user() {
  step "Service account and folders"
  if id "$SERVICE_USER" >/dev/null 2>&1; then ok "account $SERVICE_USER exists"
  else run useradd --system --home-dir "$INSTANCE_ROOT" --no-create-home --shell /usr/sbin/nologin "$SERVICE_USER"; fi
  local d
  for d in "$INSTANCE_ROOT" "$INSTANCE_ROOT/releases" "$INSTANCE_ROOT/traffic" "$INSTANCE_ROOT/status" "$PREFIX/opt/labadda"; do
    run install -d -m 0755 -o root -g root "$d"
  done
  run install -d -m 0700 -o "$SERVICE_USER" -g "$SERVICE_USER" "$INSTANCE_ROOT/assets"
  for d in "$INSTANCE_ROOT/operations" "$BACKUP_ROOT" "$ETC_DIR" "$SECRETS_DIR"; do
    run install -d -m 0700 -o root -g root "$d"
  done
  ok "folders ready under $INSTANCE_ROOT"
}

step_tools() {
  step "Operator tools (copied from the verified kit)"
  local next="$TOOLS_DIR.new" prev="$TOOLS_DIR.prev"
  if ! ((DRY_RUN)); then
    rm -rf "$next"; cp -a "$KIT/tools" "$next"; mkdir -p "$next/bin"
    cp -a "$KIT"/*.sh "$next/bin/"; cp -a "$KIT/lib" "$next/bin/lib"
    [[ -d $TOOLS_DIR ]] && { rm -rf "$prev"; mv "$TOOLS_DIR" "$prev"; }
    mv "$next" "$TOOLS_DIR"
    mkdir -p "$SBIN_DIR"
    local n
    for n in status backup-now restore upgrade; do ln -sfn "$TOOLS_DIR/bin/$n.sh" "$SBIN_DIR/labadda-$n"; done
  fi
  ok "tools in $TOOLS_DIR; commands labadda-status, labadda-backup-now, labadda-restore, labadda-upgrade"
}

step_database() {
  step "PostgreSQL role and database"
  local pw_file="$SECRETS_DIR/$SITE.db-password" db="labadda_$SITE" pg="runuser -u postgres -- psql -v ON_ERROR_STOP=1 -qtAX"
  if ((DRY_RUN)); then say "    [dry-run] would create role and database $db with a generated password in $pw_file"; return 0; fi
  if [[ -f $pw_file ]]; then ok "password file exists"; else
    if $pg -c "select 1 from pg_roles where rolname='$db'" | grep -q 1; then
      die "A database role named $db already exists but $pw_file does not. Remove the role or restore the file."; fi
    (umask 077; openssl rand -hex 24 >"$pw_file")
  fi
  DB_PASSWORD=$(<"$pw_file")
  $pg -c "select 1 from pg_roles where rolname='$db'" | grep -q 1 \
    || $pg -c "create role $db login password '$DB_PASSWORD'" >/dev/null
  $pg -c "select 1 from pg_database where datname='$db'" | grep -q 1 \
    || runuser -u postgres -- createdb -O "$db" "$db"
  ok "database $db ready; password kept in $pw_file (root only)"
}

step_config() {
  step "Site settings"
  local helper="$PYTHON $TOOLS_DIR/scripts/install_helpers.py" url
  if ((DRY_RUN)); then say "    [dry-run] would write $ENV_FILE, $SITE_JSON and $ANSWERS_FILE"; return 0; fi
  url="postgresql+psycopg://labadda_$SITE:$(<"$SECRETS_DIR/$SITE.db-password")@localhost:5432/labadda_$SITE"
  if [[ -f $ENV_FILE ]]; then ok "$ENV_FILE exists and is kept (edit it by hand to change settings)"
  else
    $helper env-file --site "$SITE" --prefix "$PREFIX" --hostname "$HOSTNAME_" --port "$PORT" --zone "$TIMEZONE_" \
      --domain "$EMAIL_DOMAIN" --database-url "$url" --example "$TOOLS_DIR/deploy/labadda.env.example" \
      | write_file 0600 root:root "$ENV_FILE"
  fi
  if [[ -f $SITE_JSON ]]; then ok "$SITE_JSON exists and is kept"
  else $helper site-json --site "$SITE" --prefix "$PREFIX" --hostname "$HOSTNAME_" --port "$PORT" --user "$SERVICE_USER" \
    | write_file 0644 root:root "$SITE_JSON"; fi
  printf 'SITE_TITLE=%s\nHOSTNAME_=%s\nTIMEZONE_=%s\nEMAIL_DOMAIN=%s\nFEEDBACK_EMAIL=%s\nSMTP_RELAY=%s\nPORT=%s\nSERVICE_USER=%s\n' \
    "$SITE_TITLE" "$HOSTNAME_" "$TIMEZONE_" "$EMAIL_DOMAIN" "$FEEDBACK_EMAIL" "$SMTP_RELAY" "$PORT" "$SERVICE_USER" \
    | write_file 0600 root:root "$ANSWERS_FILE"
  ok "answers recorded in $ANSWERS_FILE (this release does not send e-mail; they are kept for later)"
}

step_release() {
  step "Application release $VERSION"
  local archive="$KIT/release/labadda-$VERSION.tar.gz" digest
  digest=$(cut -d' ' -f1 "$archive.sha256" 2>/dev/null || cut -d' ' -f1 "${archive%.gz}.gz.sha256")
  if [[ -d $INSTANCE_ROOT/releases/$VERSION ]]; then ok "already installed"; return 0; fi
  run "$PYTHON" "$TOOLS_DIR/scripts/release.py" install "$archive" --sha256 "$digest" --instance "$INSTANCE_ROOT" >/dev/null
  ok "release $VERSION installed from the wheelhouse (no internet used)"
}

step_tls() {
  step "Certificate"
  local crt="$CERT_DIR/server.crt" key="$CERT_DIR/server.key"
  run install -d -m 0755 "$CERT_DIR"
  if [[ -n ${CERT_FILE:-} ]]; then
    run install -m 0644 "$CERT_FILE" "$crt"; run install -m 0600 "$KEY_FILE" "$key"; ok "site certificate installed"
    if [[ -n ${CA_FILE:-} ]]; then
      run install -m 0644 "$CA_FILE" "$CERT_DIR/ca.crt"
      printf '%s\n' "$CERT_DIR/ca.crt" | write_file 0644 root:root "$ETC_DIR/$SITE.probe-ca"
      LABADDA_PROBE_CA_FILE=$CERT_DIR/ca.crt; export LABADDA_PROBE_CA_FILE
    else warn "if your certificate authority is not trusted by this server, re-run with --ca-file CA.crt"; fi
  elif [[ -f $crt && -f $key ]]; then ok "certificate already in $CERT_DIR"
  else
    warn "no site certificate given: making a SELF-SIGNED one for the pilot. Browsers will warn until it is trusted."
    run openssl req -x509 -newkey rsa:3072 -nodes -days 825 -subj "/CN=$HOSTNAME_" -keyout "$key" -out "$crt" \
      -addext "subjectAltName=DNS:$HOSTNAME_" -addext "basicConstraints=critical,CA:TRUE" 2>/dev/null
    run chmod 0600 "$key"
    # The server's own probes must trust this certificate too (see operations.py probe).
    printf '%s\n' "$crt" | write_file 0644 root:root "$ETC_DIR/$SITE.probe-ca"
    LABADDA_PROBE_CA_FILE=$crt; export LABADDA_PROBE_CA_FILE
    # On a real server also trust it system-wide so the doctor's secure-connection check passes.
    if [[ -z $PREFIX ]] && ! ((DRY_RUN)); then
      install -m 0644 "$crt" /usr/local/share/ca-certificates/labadda-pilot.crt && update-ca-certificates >/dev/null
    fi
  fi
}

step_render_units() {
  step "Service, backup timer and web server files"
  local out
  out=$(mktemp -d)/review
  if ((DRY_RUN)); then say "    [dry-run] would render and install the labadda-$SITE service and nginx site"; return 0; fi
  operations render --out "$out" >/dev/null
  install -d "$SYSTEMD_DIR"
  install -m 0644 "$out/service.conf" "$SYSTEMD_DIR/$UNIT"
  install -m 0644 "$TOOLS_DIR/deploy/systemd/labadda-backup@.service" "$SYSTEMD_DIR/"
  install -m 0644 "$TOOLS_DIR/deploy/systemd/labadda-backup@.timer" "$SYSTEMD_DIR/"
  if ((NO_NGINX)); then ok "web server site skipped on request"; else
    install -d "$NGINX_DIR/conf.d"; install -m 0644 "$out/nginx.conf" "$NGINX_DIR/conf.d/labadda-$SITE.conf"
    rm -f "$NGINX_DIR/sites-enabled/default"
    nginx -t -c "${LABADDA_NGINX_MAIN_CONF:-$NGINX_DIR/nginx.conf}" >/dev/null 2>&1 \
      || { nginx -t -c "${LABADDA_NGINX_MAIN_CONF:-$NGINX_DIR/nginx.conf}"; die "nginx rejected the generated site file."; }
    ok "nginx accepts the site file"
  fi
  if [[ -f $ETC_DIR/$SITE.probe-ca ]]; then
    install -d "$SYSTEMD_DIR/labadda-backup@$SITE.service.d"
    printf '[Service]\nEnvironment=LABADDA_PROBE_CA_FILE=%s\n' "$(<"$ETC_DIR/$SITE.probe-ca")" \
      >"$SYSTEMD_DIR/labadda-backup@$SITE.service.d/probe-ca.conf"
  fi
  "$SYSTEMCTL" daemon-reload
  ok "installed $UNIT and the nightly backup timer files"
}

step_initialize() {
  step "Database content and activation"
  if [[ -L $INSTANCE_ROOT/current ]]; then ok "already activated ($(current_version))"; return 0; fi
  if ((DRY_RUN)); then say "    [dry-run] would migrate (or restore), then activate release $VERSION"; return 0; fi
  if [[ -n ${RESTORE_BUNDLE:-} ]]; then
    rm -rf "$INSTANCE_ROOT/assets"
    with_env "$PYTHON" "$TOOLS_DIR/scripts/commission.py" --site "$SITE_JSON" restore --candidate "$VERSION" \
      --bundle "$RESTORE_BUNDLE" --manifest-sha256 "$RESTORE_SHA" --apply --isolated-target >/dev/null
    chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTANCE_ROOT/assets"; chmod 0700 "$INSTANCE_ROOT/assets"
  else
    with_env "$PYTHON" "$TOOLS_DIR/scripts/commission.py" --site "$SITE_JSON" initialize --candidate "$VERSION" --apply --isolated-target >/dev/null
  fi
  local schema; schema=$(schema_of "$VERSION")
  with_env release_tool activate --instance "$INSTANCE_ROOT" --release "$VERSION" --database-schema "$schema" \
    --writers-quiesced --backup-verified >/dev/null
  ok "release $VERSION active, database schema $schema"
}

step_admin() {
  step "First administrator"
  local flag="$ETC_DIR/$SITE.admin-created"
  if [[ -n ${RESTORE_BUNDLE:-} ]]; then ok "accounts come from the restored backup"; return 0; fi
  if [[ -f $flag ]]; then ok "already created"; return 0; fi
  ask ADMIN_USER "Username for the first administrator (lowercase, no spaces)" ""
  ask ADMIN_NAME "Full name shown for that administrator" "$ADMIN_USER"
  if ((DRY_RUN)); then say "    [dry-run] would create administrator $ADMIN_USER"; return 0; fi
  say "    The one-time activation code is printed ONCE below. Give it privately to $ADMIN_NAME."
  ( cd "$INSTANCE_ROOT/current/backend" && with_env "$INSTANCE_ROOT/current/venv/bin/python" -m labadda.cli create-admin \
      "$ADMIN_USER" --display-name "$ADMIN_NAME" ) && touch "$flag"
}

step_start() {
  step "Start and health checks"
  if ((DRY_RUN)); then say "    [dry-run] would enable and start $UNIT, the backup timer and nginx"; return 0; fi
  "$SYSTEMCTL" enable --now "$UNIT" >/dev/null
  wait_for_health 90 || die "The service did not answer on its loopback port. See: journalctl -u $UNIT -n 50"
  ok "service answers (liveness and readiness)"
  rm -f "$INSTANCE_ROOT/traffic/maintenance"
  if ((NO_NGINX)); then return 0; fi
  "$SYSTEMCTL" enable --now nginx >/dev/null; "$SYSTEMCTL" reload nginx
  operations probe >/dev/null || die "The service is up but the HTTPS address https://$HOSTNAME_ does not answer; check DNS and nginx."
  ok "https://$HOSTNAME_ answers"
}

step_backup_and_doctor() {
  step "First backup and doctor"
  if ((DRY_RUN)); then say "    [dry-run] would take the first backup, enable the nightly timer and run the doctor"; return 0; fi
  lifecycle backup --unattended --apply --external-writers-stopped --resume-after-backup >/dev/null \
    && ok "first backup taken and verified" || warn "the first backup failed; run labadda-backup-now and read its message"
  if ((NO_TIMER)); then ok "nightly timer skipped on request"; else "$SYSTEMCTL" enable --now "labadda-backup@$SITE.timer" >/dev/null; fi
  ( cd "$INSTANCE_ROOT/current/backend" && "$INSTANCE_ROOT/current/venv/bin/python" -m labadda.cli doctor --env-file "$ENV_FILE" ) \
    || warn "the doctor reported problems above; fix them from the top and run: labadda-status"
}
