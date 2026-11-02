#!/usr/bin/env bash
#
# setup.sh — one-time Pico SDK setup (reuses an installed ~/.breadmodular
# Pico SDK 2.1.1 / ARM GCC 14.2 / picotool; downloads only what is missing).
#
set -euo pipefail

exec "$(dirname "${BASH_SOURCE[0]}")/../../../opt/rp2350-tools/setup.sh" "$@"
