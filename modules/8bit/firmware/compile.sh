#!/usr/bin/env bash
#
# compile.sh — build one 8bit firmware for one JP1 setting.
#
# Usage:
#   ./compile.sh                          # pick both interactively
#   ./compile.sh drums|supersaw|crash p|d
#   ./compile.sh lfo                      # no MIDI, no JP1 setting
#
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/jumper.sh" "${1:-}" "${2:-}"
exec "$TOOLS_DIR/compile.sh"
