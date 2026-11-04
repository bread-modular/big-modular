#!/usr/bin/env bash
#
# compile.sh — build a 32bit firmware (polysynth or fxrack) for one JP1 setting.
#
# Usage:
#   ./compile.sh                  # polysynth, pick JP1 interactively
#   ./compile.sh p|d              # polysynth
#   ./compile.sh fxrack p|d       # fxrack (also: p|d fxrack, polysynth p|d)
#
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/jumper.sh" "${1:-}" "${2:-}"
exec "$TOOLS_DIR/compile.sh"
