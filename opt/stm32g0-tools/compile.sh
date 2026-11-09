#!/usr/bin/env bash
#
# compile.sh — build $STM32_PROJECT_ROOT -> <build>/<target>.{elf,bin,hex}.
#
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
activate_stm32

make -C "$STM32_PROJECT_ROOT" -j"$(nproc 2>/dev/null || echo 4)" \
  CROSS_COMPILE="$ARM_TOOLCHAIN/bin/arm-none-eabi-" \
  CMSIS_G0_PATH="$CMSIS_G0_PATH" CMSIS_CORE_PATH="$CMSIS_CORE_PATH" \
  BUILD="$STM32_BUILD_DIR" TARGET="$STM32_TARGET" DEFINES="${STM32_DEFINES:-}" "$@"

echo "Built $STM32_BUILD_DIR/$STM32_TARGET.elf"
