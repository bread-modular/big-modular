#!/usr/bin/env bash
#
# compile.sh — build the cpx4 MCC firmware for one JP1 setting and unit.
#
# Usage:
#   ./compile.sh            # pick JP1 and the unit interactively
#   ./compile.sh p|d 1|2    # 1 = MCC-1 VOICE, 2 = MCC-2 FX
#
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/jumper.sh" "${1:-}" "${2:-}"
exec "$TOOLS_DIR/compile.sh"
