#!/usr/bin/env bash
# Build the install bundle on a CONNECTED Ubuntu 24.04 x86-64 build machine.
#   scripts/make-release-bundle.sh OUTPUT_FOLDER                 mirror mode (default): small bundle
#   scripts/make-release-bundle.sh OUTPUT_FOLDER --offline-kit   fallback: adds wheelhouse and .deb files
# Needs: a clean committed checkout, Node 22 (npm), a Python 3.12 environment with the backend
# requirements installed (README: .venv), internet for the dependency age check, and for --offline-kit
# also dpkg-dev and the Ubuntu package sources. The build stops if any pinned dependency is younger
# than 30 days (docs/RELEASES.md). Result: <output>/labadda-<version>-bundle or ...-offline-kit.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-}"
[[ -n $OUT ]] || { sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'; exit 2; }
PY="${LABADDA_PYTHON:-$ROOT/.venv/bin}/python"
[[ -x $PY ]] || PY="$(command -v python3.12)"
"$PY" -c 'import sys;sys.exit(sys.version_info[:2]!=(3,12))' || { echo "Need Python 3.12 (set LABADDA_PYTHON to a venv bin folder)." >&2; exit 1; }
if [[ " $* " == *" --offline-kit "* ]]; then
  command -v dpkg-scanpackages >/dev/null || { echo "Install dpkg-dev first: sudo apt-get install dpkg-dev" >&2; exit 1; }
fi
mkdir -p "$OUT"
echo "Building version $("$PY" "$ROOT/scripts/kit.py" version) ..."
# The build prints a lot (npm, pip, apt); its last line is the folder.
KIT="$("$PY" "$ROOT/scripts/kit.py" build --output "$OUT" --root "$ROOT" "${@:2}" | tee /dev/stderr | tail -n 1)"
"$PY" "$ROOT/scripts/kit.py" verify "$KIT"
echo
echo "Ready: $KIT"
echo "Fingerprint (write it down, check it on the server): $(sha256sum "$KIT/SHA256SUMS" | cut -d' ' -f1)"
du -sh "$KIT"
