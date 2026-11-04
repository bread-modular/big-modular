#!/usr/bin/env bash
#
# flash.sh — build and flash a 32bit firmware (polysynth or fxrack) over the USB-C port.
#
# Usage:
#   ./flash.sh                               # pick JP1, the firmware and the port from menus
#   ./flash.sh p|d                           # pick the firmware (Enter = polysynth) and the port
#   ./flash.sh p|d fxrack|polysynth [port]   # no firmware menu (also: fxrack p|d [port])
#   ./flash.sh p fxrack /dev/ttyACM0         # explicit port (macOS: /dev/cu.usbmodemXXXX)
#   MONITOR=1 ./flash.sh p fxrack            # open the serial monitor after flashing
#
set -euo pipefail

ASK_FIRMWARE=1 source "$(dirname "${BASH_SOURCE[0]}")/jumper.sh" "${1:-}" "${2:-}"
exec "$TOOLS_DIR/flash.sh" "${@:$((JUMPER_ARGC + 1))}"
