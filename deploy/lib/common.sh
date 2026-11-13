# Shared helpers for the LabAdda on-server scripts. Sourced, never run on its own.
# Every system path can be moved under LABADDA_ROOT_PREFIX so the scripts can be rehearsed in a
# scratch folder; on the real server the prefix is empty.
set -euo pipefail

PREFIX="${LABADDA_ROOT_PREFIX:-}"
DRY_RUN=0
ASSUME_YES=0
SITE="${LABADDA_SITE:-main}"
SYSTEMCTL="${LABADDA_SYSTEMCTL:-systemctl}"
PYTHON="${LABADDA_PYTHON312:-python3.12}"

say() { printf '%s\n' "$*"; }
step() { printf '\n==> %s\n' "$*"; }
ok() { printf '    OK: %s\n' "$*"; }
warn() { printf '    NOTE: %s\n' "$*" >&2; }
die() { printf '\nSTOPPED: %s\n' "$*" >&2; exit 1; }

# Run a command that changes the machine; with --dry-run only say what would happen.
run() {
  if ((DRY_RUN)); then printf '    [dry-run] would run: %s\n' "$*"; else "$@"; fi
}

# Write stdin to a file atomically with a mode and owner (user:group).
write_file() {
  local mode=$1 owner=$2 dest=$3 tmp
  if ((DRY_RUN)); then
    cat >/dev/null
    printf '    [dry-run] would write %s (mode %s)\n' "$dest" "$mode"
    return 0
  fi
  mkdir -p "$(dirname "$dest")"
  tmp=$(mktemp "$dest.XXXXXX")
  cat >"$tmp"
  chmod "$mode" "$tmp"
  chown "$owner" "$tmp"
  mv -f "$tmp" "$dest"
}

need_root() {
  if ((DRY_RUN)); then return 0; fi
  [[ $(id -u) -eq 0 ]] || die "Run this with sudo, for example: sudo bash $0"
}

set_paths() {
  ETC_DIR="$PREFIX/etc/labadda"
  SITE_JSON="$ETC_DIR/$SITE.site.json"
  ENV_FILE="$ETC_DIR/$SITE.env"
  ANSWERS_FILE="$ETC_DIR/$SITE.install.conf"
  SECRETS_DIR="$ETC_DIR/secrets"
  TOOLS_DIR="$PREFIX/opt/labadda/tools"
  SYSTEMD_DIR="$PREFIX/etc/systemd/system"
  NGINX_DIR="$PREFIX/etc/nginx"
  CERT_DIR="$PREFIX/etc/ssl/labadda"
  SBIN_DIR="$PREFIX/usr/local/sbin"
  INSTANCE_ROOT="$PREFIX/srv/labadda/$SITE"
  BACKUP_ROOT="$PREFIX/srv/labadda-backups/$SITE"
  UNIT="labadda-$SITE.service"
}

# Read one field from the site description written by the installer.
site_field() { "$PYTHON" -c 'import json,sys;print(json.load(open(sys.argv[1]))[sys.argv[2]])' "$SITE_JSON" "$1"; }

lifecycle() { "$PYTHON" "$TOOLS_DIR/scripts/lifecycle.py" --site "$SITE_JSON" "$@"; }
operations() { "$PYTHON" "$TOOLS_DIR/scripts/operations.py" --site "$SITE_JSON" "$@"; }
release_tool() { "$PYTHON" "$TOOLS_DIR/scripts/release.py" "$@"; }

# Run a command with the site settings loaded; values are plain KEY=value lines, so sourcing is safe.
with_env() { (
  set -a
  # shellcheck disable=SC1090
  . "$ENV_FILE"
  set +a
  "$@"
); }

current_version() {
  local link="$INSTANCE_ROOT/current"
  [[ -L $link ]] || { echo "none"; return; }
  basename "$(readlink -f "$link")"
}

# Observed database schema of a release, read through that release's own checks.
schema_of() { with_env release_tool preflight --instance "$INSTANCE_ROOT" --release "$1" | sed 's/^Observed database schema: //'; }

wait_for_health() {
  local seconds=${1:-90} i
  for ((i = 0; i < seconds; i += 2)); do
    if operations probe --direct >/dev/null 2>&1; then return 0; fi
    sleep 2
  done
  return 1
}

# Ask for a value unless it is already set; --yes and a missing terminal use the default.
ask() {
  local var=$1 question=$2 default=${3:-} reply
  if [[ -n ${!var:-} ]]; then return 0; fi
  if ((ASSUME_YES)) || [[ ! -t 0 ]]; then
    [[ -n $default ]] || die "No answer for: $question (give it with --answers or run in a terminal)"
    printf -v "$var" '%s' "$default"
    return 0
  fi
  read -r -p "$question${default:+ [$default]}: " reply
  printf -v "$var" '%s' "${reply:-$default}"
}

# Answers files hold only KEY=value lines for known names; they are read, never executed.
load_answers() {
  local file=$1 key value
  [[ -f $file ]] || die "Answers file not found: $file"
  while IFS='=' read -r key value; do
    [[ -z $key || $key == \#* ]] && continue
    case $key in
      SITE_TITLE | HOSTNAME_ | TIMEZONE_ | EMAIL_DOMAIN | FEEDBACK_EMAIL | SMTP_RELAY | PORT | SERVICE_USER | ADMIN_USER | ADMIN_NAME)
        [[ $value =~ ^[A-Za-z0-9@._:/\ -]*$ ]] || die "Answers file: odd characters in $key"
        [[ -n ${!key:-} ]] || printf -v "$key" '%s' "$value" ;;
      *) die "Answers file: unknown setting $key" ;;
    esac
  done <"$file"
}

verify_kit() {
  local kit=$1
  [[ -f $kit/MANIFEST.json && -f $kit/SHA256SUMS ]] || die "$kit is not a LabAdda kit (no MANIFEST.json)."
  ( cd "$kit" && sha256sum --quiet -c SHA256SUMS ) || die "The kit is damaged or incomplete. Copy it again from the original and retry."
  "$PYTHON" "$kit/tools/scripts/kit.py" verify "$kit" >/dev/null || die "The kit failed its deeper check (run kit.py verify to see which file)."
  ok "all kit files match their checksums ($(sha256sum "$kit/SHA256SUMS" | cut -c1-16)... is the kit's fingerprint)"
}

kit_field() { "$PYTHON" -c 'import json,sys;print(json.load(open(sys.argv[1]+"/MANIFEST.json"))[sys.argv[2]])' "$1" "$2"; }
