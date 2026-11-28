#!/usr/bin/env bash
#
# flash.sh — build and flash the MOTION firmware via UPDI (J6) with the shared
# opt/attiny1616-tools/flash.sh.
#
# Usage:
#   ./flash.sh                           # pick the port
#   ./flash.sh /dev/ttyACM0              # explicit port
#   PROGRAMMER=serialupdi ./flash.sh     # see opt/attiny1616-tools/flash.sh
#
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/../../../opt/checkout-owner.sh"
require_checkout_owner "$@"

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export ATTINY_SKETCH_ROOT="$HERE"
exec "$HERE/../../../opt/attiny1616-tools/flash.sh" "$@"
