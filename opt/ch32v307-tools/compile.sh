#!/usr/bin/env bash
#
# compile.sh — build $CH32_PROJECT_ROOT -> <build>/<target>.{elf,bin,hex}.
#
set -euo pipefail

TOOLS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../checkout-owner.sh
source "$TOOLS_DIR/../checkout-owner.sh"
require_checkout_owner "$@"
source "$TOOLS_DIR/common.sh"
# shellcheck source=../build-dir.sh
source "$TOOLS_DIR/../build-dir.sh"
activate_ch32

# make does not see a compiler, TinyUSB or SDK change (a pinned version bump;
# os and home ship the same pinned set): a build dir recorded with other tools
# is removed first (opt/build-dir.sh).
check_make_build_dir "$CH32_BUILD_DIR" "$CH32_PROJECT_ROOT" \
  "gcc=$CH32_TOOLCHAIN/bin/riscv-none-elf-gcc $("$CH32_TOOLCHAIN/bin/riscv-none-elf-gcc" -dumpversion)" \
  "tinyusb=$TINYUSB_PATH" "wch_sdk=$WCH_SDK_PATH"

echo "==> riscv-none-elf-gcc: $CH32_TOOLCHAIN/bin/riscv-none-elf-gcc ($("$CH32_TOOLCHAIN/bin/riscv-none-elf-gcc" -dumpversion), $CH32_TOOLCHAINS toolchains)"
echo "==> TinyUSB: $TINYUSB_PATH, WCH SDK: $WCH_SDK_PATH"

make -C "$CH32_PROJECT_ROOT" -j"$(nproc 2>/dev/null || echo 4)" \
  CROSS_COMPILE="$CH32_TOOLCHAIN/bin/riscv-none-elf-" \
  TINYUSB_PATH="$TINYUSB_PATH" WCH_SDK_PATH="$WCH_SDK_PATH" \
  BUILD="$CH32_BUILD_DIR" TARGET="$CH32_TARGET" "$@"

echo "Built $CH32_BUILD_DIR/$CH32_TARGET.bin"
