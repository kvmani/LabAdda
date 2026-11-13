#!/usr/bin/env bash
# Build the offline install kit on a CONNECTED Ubuntu 24.04 x86-64 build machine.
#   scripts/make-offline-kit.sh /path/to/output-folder
# Needs: a clean committed checkout, Node 22 (npm), dpkg-dev, a Python 3.12 environment with the backend
# requirements installed (README: .venv), and access to the Ubuntu and Python package sources.
# Result: <output>/labadda-<version>-offline-kit/ (the version comes from backend/labadda/__init__.py).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-}"
[[ -n $OUT ]] || { sed -n '2,7p' "$0" | sed 's/^# \{0,1\}//'; exit 2; }
PY="${LABADDA_PYTHON:-$ROOT/.venv/bin}/python"
[[ -x $PY ]] || PY="$(command -v python3.12)"
"$PY" -c 'import sys;sys.exit(sys.version_info[:2]!=(3,12))' || { echo "Need Python 3.12 (set LABADDA_PYTHON to a venv bin folder)." >&2; exit 1; }
command -v dpkg-scanpackages >/dev/null || { echo "Install dpkg-dev first: sudo apt-get install dpkg-dev" >&2; exit 1; }
mkdir -p "$OUT"
echo "Building the kit for version $("$PY" "$ROOT/scripts/kit.py" version) ..."
# The build prints a lot (npm, pip, apt); its last line is the kit folder.
KIT="$("$PY" "$ROOT/scripts/kit.py" build --output "$OUT" --root "$ROOT" "${@:2}" | tee /dev/stderr | tail -n 1)"
"$PY" "$ROOT/scripts/kit.py" verify "$KIT"
echo
echo "Kit ready: $KIT"
echo "Kit fingerprint (write it down, check it on the server): $(sha256sum "$KIT/SHA256SUMS" | cut -d' ' -f1)"
du -sh "$KIT"
