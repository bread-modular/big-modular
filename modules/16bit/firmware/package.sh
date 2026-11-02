#!/usr/bin/env bash
#
# package.sh — build one firmware per app for one JP1 setting into
# 16bit/dist/<app>_<version>_<p|d>/16bit.uf2 (as Bread Modular package.sh).
#
# Usage:
#   ./package.sh p|d             # all apps
#   ./package.sh p|d app ...     # some apps
#
set -euo pipefail

FW_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SETTING="${1:-}"
[[ -n "$SETTING" ]] || { echo "Usage: ./package.sh p|d [app ...]" >&2; exit 1; }
shift
VERSION="$(tr -d '[:space:]' < "$FW_DIR/16bit/VERSION")"

if [[ $# -eq 0 ]]; then
  source "$FW_DIR/jumper.sh" "$SETTING" polysynth >/dev/null
  set -- "${APPS[@]}"
fi

for app in "$@"; do
  "$FW_DIR/compile.sh" "$SETTING" "$app"
  "$FW_DIR/webapi-check.sh" "$app"
  out="$FW_DIR/16bit/dist/${app}_${VERSION}_${SETTING}"
  mkdir -p "$out"
  cp "$FW_DIR/16bit/.build/16bit.uf2" "$out/16bit.uf2"
  echo "==> Packaged $out/16bit.uf2"
done
