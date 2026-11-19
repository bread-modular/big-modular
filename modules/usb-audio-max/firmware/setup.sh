#!/usr/bin/env bash
#
# setup.sh — one-time CH32V307 toolchain setup (xPack RISC-V GCC, TinyUSB,
# WCH SDK, wchisp; reuses what is installed, downloads only what is missing).
#
set -euo pipefail

exec "$(dirname "${BASH_SOURCE[0]}")/../../../opt/ch32v307-tools/setup.sh" "$@"
