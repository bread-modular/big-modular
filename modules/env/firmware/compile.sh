#!/usr/bin/env bash
#
# compile.sh — build the ENV firmware for one JP1 setting.
#
# Usage:
#   ./compile.sh        # pick JP1 interactively
#   ./compile.sh p|d
#
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/../../../opt/checkout-owner.sh"
require_checkout_owner "$@"

source "$(dirname "${BASH_SOURCE[0]}")/jumper.sh" "${1:-}"
exec "$TOOLS_DIR/compile.sh"
