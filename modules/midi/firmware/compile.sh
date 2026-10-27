#!/usr/bin/env bash
#
# compile.sh — build the MIDI firmware for one hardware version.
#
# Usage:
#   ./compile.sh                  # pick the version interactively
#   ./compile.sh v1|v2|v2-direct
#
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/version.sh" "${1:-}"
exec "$TOOLS_DIR/compile.sh"
