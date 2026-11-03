#!/usr/bin/env bash
#
# flash.sh — build and flash one HATS firmware via UPDI.
#
# Usage:
#   ./flash.sh                                  # pick firmware, JP1 and port
#   ./flash.sh noise|hihat p|d             # pick the port
#   ./flash.sh hihat p /dev/ttyACM0             # explicit port
#   PROGRAMMER=serialupdi ./flash.sh noise d    # see opt/attiny1616-tools/flash.sh
#
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/jumper.sh" "${1:-}" "${2:-}"
exec "$TOOLS_DIR/flash.sh" "${@:$((JUMPER_ARGC + 1))}"
