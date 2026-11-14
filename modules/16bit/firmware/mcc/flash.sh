#!/usr/bin/env bash
#
# flash.sh — build and flash the lyra4 MCC firmware via UPDI.
#
# Usage:
#   ./flash.sh                            # pick JP1, the unit and the port
#   ./flash.sh p|d 1|2                    # pick the port
#   ./flash.sh p 1 /dev/ttyACM0           # explicit port
#   PROGRAMMER=serialupdi ./flash.sh d 2  # see opt/attiny1616-tools/flash.sh
#
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/jumper.sh" "${1:-}" "${2:-}"
exec "$TOOLS_DIR/flash.sh" "${@:3}"
