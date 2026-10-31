#!/usr/bin/env bash
#
# flash.sh — build and flash the 32bit polysynth firmware over the USB-C port.
#
# Usage:
#   ./flash.sh                        # pick JP1 and port
#   ./flash.sh p|d                    # pick the port
#   ./flash.sh p /dev/ttyACM0         # explicit port (macOS: /dev/cu.usbmodemXXXX)
#   MONITOR=1 ./flash.sh p            # open the serial monitor after flashing
#
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/jumper.sh" "${1:-}"
exec "$TOOLS_DIR/flash.sh" "${@:2}"
