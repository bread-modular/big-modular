#!/usr/bin/env bash
#
# flash.sh — build the HATS firmware for one JP1 setting and flash U2 over
# SWD (ST-Link on J11), with the module on Eurorack power.
#
# Usage:
#   ./flash.sh            # pick JP1 interactively
#   ./flash.sh p|d
#
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/jumper.sh" "${1:-}"
exec "$TOOLS_DIR/flash.sh"
