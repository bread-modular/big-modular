#!/usr/bin/env bash
#
# flash.sh — build one 12bit firmware and flash U3 over SWD (J6), with the
# module on Eurorack power. The default probe is CMSIS-DAP (DAPLink); for an
# ST-Link: OPENOCD_INTERFACE=interface/stlink.cfg ./flash.sh ...
#
# Usage:
#   ./flash.sh                    # pick firmware and JP1 interactively
#   ./flash.sh clapsnare p|d
#   ./flash.sh crash     p|d
#   ./flash.sh osc3               # no MIDI, no JP1 setting
#   ./flash.sh humtest            # output noise bench test, no JP1 setting
#
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/../../../opt/checkout-owner.sh"
require_checkout_owner "$@"

source "$(dirname "${BASH_SOURCE[0]}")/jumper.sh" "${1:-}" "${2:-}"
export OPENOCD_INTERFACE="${OPENOCD_INTERFACE:-interface/cmsis-dap.cfg}"
exec "$TOOLS_DIR/flash.sh"
