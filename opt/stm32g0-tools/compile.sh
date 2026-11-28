#!/usr/bin/env bash
#
# compile.sh — build $STM32_PROJECT_ROOT -> <build>/<target>.{elf,bin,hex}.
#
set -euo pipefail

TOOLS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../checkout-owner.sh
source "$TOOLS_DIR/../checkout-owner.sh"
require_checkout_owner "$@"
source "$TOOLS_DIR/common.sh"
# shellcheck source=../build-dir.sh
source "$TOOLS_DIR/../build-dir.sh"
activate_stm32

# make does not see a compiler or CMSIS change (BIG_MODULAR_TOOLCHAINS os vs
# home: GCC 16.2 vs 14.2) and would link the old objects with the new libraries:
# a build dir recorded with other tools is removed first (opt/build-dir.sh).
check_make_build_dir "$STM32_BUILD_DIR" "$STM32_PROJECT_ROOT" \
  "gcc=$ARM_TOOLCHAIN/bin/arm-none-eabi-gcc $("$ARM_TOOLCHAIN/bin/arm-none-eabi-gcc" -dumpversion)" \
  "cmsis_g0=$CMSIS_G0_PATH" "cmsis_core=$CMSIS_CORE_PATH"

echo "==> arm-none-eabi-gcc: $ARM_TOOLCHAIN/bin/arm-none-eabi-gcc ($("$ARM_TOOLCHAIN/bin/arm-none-eabi-gcc" -dumpversion), $STM32_TOOLCHAINS toolchains)"
echo "==> CMSIS: $CMSIS_G0_PATH, $CMSIS_CORE_PATH"

make -C "$STM32_PROJECT_ROOT" -j"$(nproc 2>/dev/null || echo 4)" \
  CROSS_COMPILE="$ARM_TOOLCHAIN/bin/arm-none-eabi-" \
  CMSIS_G0_PATH="$CMSIS_G0_PATH" CMSIS_CORE_PATH="$CMSIS_CORE_PATH" \
  BUILD="$STM32_BUILD_DIR" TARGET="$STM32_TARGET" DEFINES="${STM32_DEFINES:-}" "$@"

echo "Built $STM32_BUILD_DIR/$STM32_TARGET.elf"
