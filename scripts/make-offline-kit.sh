#!/usr/bin/env bash
# Fallback for a server with no package mirrors: same as make-release-bundle.sh with --offline-kit.
#   scripts/make-offline-kit.sh OUTPUT_FOLDER
exec "$(dirname "$0")/make-release-bundle.sh" "${1:-}" --offline-kit "${@:2}"
