#!/usr/bin/env bash
#
# flash.sh — build and flash one 8bit firmware via UPDI.
#
# Usage:
#   ./flash.sh                                  # pick firmware, JP1 and port
#   ./flash.sh drums|supersaw|crash p|d         # pick the port
#   ./flash.sh crash p /dev/ttyACM0             # explicit port
#   PROGRAMMER=serialupdi ./flash.sh drums d    # see opt/attiny1616-tools/flash.sh
#
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/jumper.sh" "${1:-}" "${2:-}"
exec "$TOOLS_DIR/flash.sh" "${@:3}"
