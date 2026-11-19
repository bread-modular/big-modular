#!/usr/bin/env bash
#
# compile.sh — build one 12bit firmware (for one JP1 setting).
#
# Usage:
#   ./compile.sh                  # pick both interactively
#   ./compile.sh clapsnare p|d
#   ./compile.sh crash     p|d
#   ./compile.sh osc3             # no MIDI, no JP1 setting
#   ./compile.sh humtest          # output noise bench test, no JP1 setting
#
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/jumper.sh" "${1:-}" "${2:-}"
exec "$TOOLS_DIR/compile.sh"
