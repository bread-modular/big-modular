#!/usr/bin/env bash
#
# flash.sh — build the 16bit firmware and load it over the module's USB-C.
#
# Usage:
#   ./flash.sh                          # pick JP1 and the app from menus, build + load
#   ./flash.sh p|d                      # pick the app from a menu, build + load
#   ./flash.sh p|d app                  # build + load that app, no menu
#   ./flash.sh 16bit/dist/polysynth_1.6.0_p/16bit.uf2   # load a packaged UF2
#   ./flash.sh info                     # show which firmware is on the board
#
# Before loading, the UF2's program info is printed, e.g.
#   name: 16bit / version: 1.6.0 / description: polysynth app, JP1=p
#
set -euo pipefail

FW_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ "${1:-}" == *.uf2 || "${1:-}" == info ]]; then
  export RP2350_PROJECT_ROOT="$FW_DIR/16bit" RP2350_TARGET=16bit
  exec "$FW_DIR/../../../opt/rp2350-tools/flash.sh" "$1"
fi
ASK_APP=1 source "$FW_DIR/jumper.sh" "${1:-}" "${2:-}"
exec "$TOOLS_DIR/flash.sh"
