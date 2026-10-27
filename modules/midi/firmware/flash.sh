#!/usr/bin/env bash
#
# flash.sh — build and flash the MIDI firmware for one hardware version via UPDI.
#
# Usage:
#   ./flash.sh                              # pick the version and the port
#   ./flash.sh v1|v2|v2-direct              # pick the port
#   ./flash.sh v2 /dev/ttyACM0              # explicit version and port
#   PROGRAMMER=serialupdi ./flash.sh v1     # see opt/attiny1616-tools/flash.sh
#
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/version.sh" "${1:-}"
exec "$TOOLS_DIR/flash.sh" "${@:2}"
