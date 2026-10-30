#!/usr/bin/env bash
#
# flash.sh — build and flash the LOW mco firmware via UPDI.
#
# Usage:
#   ./flash.sh                            # pick JP1 and port
#   ./flash.sh p|d                        # pick the port
#   ./flash.sh p /dev/ttyACM0             # explicit port
#   PROGRAMMER=serialupdi ./flash.sh d    # see opt/attiny1616-tools/flash.sh
#
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/jumper.sh" "${1:-}"
exec "$TOOLS_DIR/flash.sh" "${@:2}"
