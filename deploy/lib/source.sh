# Install or upgrade straight from GitHub's release "Source code (zip)", on a server without git or
# internet: verify the zip, check the machine, build the verified bundle beside the live site from the
# office mirrors, then hand over to that bundle's own install.sh or upgrade.sh. Sourced after common.sh.
#
#   sudo bash LabAdda-X.Y.Z/deploy/upgrade.sh --zip ~/LabAdda-X.Y.Z.zip --sha256 <published hash> [--dry-run]
#
# Use the configured Python mirror for both the build and installation. npm uses the
# operator’s internal registry unless NPM_REGISTRY is provided.

MIN_NODE_MAJOR=18
BUILD_ROOT="${LABADDA_BUILD_ROOT:-$PREFIX/var/tmp/labadda-builds}"

# Drop --zip/--sha256 (and their values) so the built bundle's own script gets the other options.
without_zip_options() {
  local skip=0 a
  for a in "$@"; do
    if ((skip)); then skip=0; continue; fi
    case $a in --zip | --sha256) skip=1 ;; *) printf '%s\0' "$a" ;; esac
  done
}

build_user() { echo "${SUDO_USER:-root}"; }
as_builder() { if [[ $(build_user) == root ]]; then "$@"; else (cd /tmp && runuser -u "$(build_user)" -- "$@"); fi; }

# Answers the mirrors at all (an error page counts: the host is there); unreachable is a stop.
mirror_answers() {
  "$PYTHON" -I - "$1" <<'PYTHON'
import sys, urllib.error, urllib.request
try:
    urllib.request.urlopen(urllib.request.Request(sys.argv[1], method="GET"), timeout=10).close()
except urllib.error.HTTPError as error:
    sys.exit(0 if error.code < 500 else 1)
except (OSError, ValueError):
    sys.exit(1)
PYTHON
}

preflight_build() {
  step "Checking this machine can build the release (nothing is changed)"
  local free_gb node_major
  command -v "$PYTHON" >/dev/null || die "python3.12 is missing. Install it from the Ubuntu mirror."
  "$PYTHON" -c 'import ensurepip, venv' 2>/dev/null || die "python3.12-venv is missing: sudo apt-get install python3.12-venv"
  command -v node >/dev/null && command -v npm >/dev/null \
    || die "Node.js and npm are needed to build the screens: sudo apt-get install nodejs npm (from the Ubuntu mirror)."
  node_major=$(node -p 'process.versions.node.split(".")[0]')
  ((node_major >= MIN_NODE_MAJOR)) || die "Node.js $node_major is too old; $MIN_NODE_MAJOR or newer is needed."
  mkdir -p "$BUILD_ROOT"
  free_gb=$(df -Pk "$BUILD_ROOT" | awk 'NR==2{print int($4/1048576)}')
  ((free_gb >= 3)) || die "Only ${free_gb} GB free under $BUILD_ROOT; the build needs 3 GB (set LABADDA_BUILD_ROOT elsewhere)."
  ok "python3.12 with venv, Node.js $(node -v), npm $(npm -v), ${free_gb} GB free for the build"
  [[ $MODE == mirror ]] || die "A source ZIP needs the internal mirrors. Use a prepared kit for --offline-kit."
  ask PIP_INDEX_URL "Internal Python package mirror address" ""
  NPM_REGISTRY=${NPM_REGISTRY:-$(as_builder npm config get registry)}
  "$PYTHON" -I - "$PIP_INDEX_URL" "$NPM_REGISTRY" <<'PYTHON' || die "Configure internal Python and npm mirrors before building."
import os
import sys
from urllib.parse import urlsplit

for address in sys.argv[1:]:
    url = urlsplit(address)
    host = url.hostname or ""
    if (url.scheme not in {"http", "https"} or not host
        or (os.environ.get("LABADDA_ALLOW_PUBLIC_INDEX") != "1"
            and any(host == public or host.endswith("." + public)
                    for public in ("pypi.org", "pythonhosted.org", "npmjs.org", "npmjs.com")))):
        sys.exit(1)
PYTHON
  mirror_answers "$PIP_INDEX_URL" || die "The internal Python package mirror does not answer."
  ok "Internal Python and npm mirrors configured"
}

verify_zip() {
  [[ -f $ZIP ]] || die "No zip at $ZIP."
  [[ $ZIP_SHA =~ ^[0-9a-f]{64}$ ]] || die "Give --sha256 with the 64-character hash published with the release."
  local actual; actual=$(sha256sum "$ZIP" | cut -d' ' -f1)
  [[ $actual == "$ZIP_SHA" ]] || die "The zip's SHA-256 is $actual, not the published $ZIP_SHA. Do not use this zip."
  read -r ZIP_COMMIT ZIP_DATE < <("$PYTHON" -I "$SELF_ROOT/scripts/source_zip.py" identity "$ZIP") \
    || die "This is not GitHub's 'Source code (zip)' of a LabAdda release."
  ok "zip matches the published hash; commit ${ZIP_COMMIT:0:12} of $ZIP_DATE"
}

# Build the bundle from the zip as the operator, from the mirrors, and print its folder.
build_kit_from_zip() {
  local work tree venv env=(PIP_CONFIG_FILE=/dev/null PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_EXTRA_INDEX_URL= PIP_FIND_LINKS= NPM_CONFIG_AUDIT=false NPM_CONFIG_FUND=false)
  work=$(mktemp -d "$BUILD_ROOT/${ZIP_COMMIT:0:12}.XXXXXX")
  install -m 0644 "$ZIP" "$work/source.zip"
  [[ $(sha256sum "$work/source.zip" | cut -d' ' -f1) == "$ZIP_SHA" ]] \
    || die "The source archive changed during transfer into the build directory."
  chown "$(build_user):$(build_user)" "$work"
  chmod 0755 "$work"
  tree=$(as_builder "$PYTHON" -I "$SELF_ROOT/scripts/source_zip.py" extract "$work/source.zip" "$work/lock") \
    || die "Could not unpack the zip."
  [[ -z ${PIP_INDEX_URL:-} ]] || env+=(PIP_INDEX_URL="$PIP_INDEX_URL")
  [[ -z ${PIP_TRUSTED_HOST:-} ]] || env+=(PIP_TRUSTED_HOST="$PIP_TRUSTED_HOST")
  [[ -z ${NPM_REGISTRY:-} ]] || env+=(NPM_CONFIG_REGISTRY="$NPM_REGISTRY")
  venv="$work/venv"
  say "    Building release from the mirrors (a few minutes; log: $work/build.log)" >&2
  {
    as_builder "$PYTHON" -m venv "$venv" \
      && as_builder env "${env[@]}" "$venv/bin/python" -m pip install -q --only-binary=:all: --no-deps \
        -r "$tree/backend/requirements.lock" \
      && as_builder env "${env[@]}" "$venv/bin/python" "$tree/scripts/kit.py" build --output "$work/out" \
        --source-zip "$work/source.zip"
  } >"$work/build.log" 2>&1 || { tail -25 "$work/build.log" >&2; die "The build failed (full log: $work/build.log). The live site was not touched."; }
  find "$work/out" -mindepth 1 -maxdepth 1 -type d -name 'labadda-*-bundle' | head -1
}

# Entry point used by install.sh and upgrade.sh when --zip is given.
from_source_zip() {
  local action=$1; shift
  need_root
  step "Checking the release zip"
  verify_zip
  preflight_build
  if ((DRY_RUN)); then
    say "    [dry-run] would build the release from the zip, then run its $action.sh with your options."
    [[ $action != upgrade ]] || preflight_upgrade
    exit 0
  fi
  step "Building the release beside the live site"
  local kit; kit=$(build_kit_from_zip)
  [[ -n $kit && -f $kit/$action.sh ]] || die "The build finished without a bundle."
  ok "bundle ready: $kit"
  local rest=()
  mapfile -d '' rest < <(without_zip_options "$@")
  exec bash "$kit/$action.sh" "${rest[@]}" --pip-index-url "$PIP_INDEX_URL" --pip-trusted-host "$PIP_TRUSTED_HOST"
}
