#!/usr/bin/env bash
#
# compile.sh — build $CH32_PROJECT_ROOT -> <build>/<target>.{elf,bin,hex}.
#
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
activate_ch32

make -C "$CH32_PROJECT_ROOT" -j"$(nproc 2>/dev/null || echo 4)" \
  CROSS_COMPILE="$CH32_TOOLCHAIN/bin/riscv-none-elf-" \
  TINYUSB_PATH="$TINYUSB_PATH" WCH_SDK_PATH="$WCH_SDK_PATH" \
  BUILD="$CH32_BUILD_DIR" TARGET="$CH32_TARGET" "$@"

echo "Built $CH32_BUILD_DIR/$CH32_TARGET.bin"
