#!/usr/bin/env bash
#
# compile.sh — build the 16bit firmware (one app) for one JP1 setting.
#
# Usage:
#   ./compile.sh                 # pick JP1 interactively, app from .config / polysynth
#   ./compile.sh p|d [app]       # app: noop sampler polysynth fxrack elab monosynth cpx4
#
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/jumper.sh" "${1:-}" "${2:-}"
exec "$TOOLS_DIR/compile.sh"
