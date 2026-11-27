#!/usr/bin/env bash
#
# setup.sh — one-time setup: the shared opt/stm32g0-tools (azero: checks the OS
# packages; elsewhere reuses the ~/.breadmodular ARM GCC and downloads the
# pinned CMSIS headers and OpenOCD).
#
set -euo pipefail

exec "$(dirname "${BASH_SOURCE[0]}")/../../../opt/stm32g0-tools/setup.sh"
