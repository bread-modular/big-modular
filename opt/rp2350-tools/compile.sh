#!/usr/bin/env bash
# compile.sh — configure + build an RP2350 Pico SDK project (see common.sh for
# the env). Output: $RP2350_BUILD_DIR/<target>.uf2 (and .elf / .bin / .hex).
set -euo pipefail

TOOLS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$TOOLS_DIR/common.sh"

resolve_project
activate_pico

CONFIGURE_ARGS=(-S "$PROJECT_DIR" -B "$BUILD_DIR"
                -DPICO_SDK_PATH="$PICO_SDK_PATH" -DPICO_TOOLCHAIN_PATH="$PICO_TOOLCHAIN_PATH")
if [[ ! -f "$BUILD_DIR/CMakeCache.txt" ]]; then
  if [[ -n "$NINJA_BIN" ]]; then
    CONFIGURE_ARGS+=(-G Ninja -DCMAKE_MAKE_PROGRAM="$NINJA_BIN")
  else
    CONFIGURE_ARGS+=(-G "Unix Makefiles")
  fi
fi
# Reuse the installed picotool; without the hint the SDK downloads and builds
# picotool from source on every fresh build dir.
if [[ -n "$PICOTOOL_BIN" && -f "$(dirname "$PICOTOOL_BIN")/picotoolConfig.cmake" ]]; then
  CONFIGURE_ARGS+=(-Dpicotool_DIR="$(dirname "$PICOTOOL_BIN")")
fi
CONFIGURE_ARGS+=("${CMAKE_DEFINE_ARGS[@]+"${CMAKE_DEFINE_ARGS[@]}"}")

JOBS="${JOBS:-$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)}"

echo "==> Pico SDK $PICO_SDK_PATH"
echo "==> Toolchain $PICO_TOOLCHAIN_PATH ($(arm-none-eabi-gcc -dumpversion))"
echo "==> Building $PROJECT_DIR (target: $BUILD_TARGET${RP2350_DEFINES:+, $RP2350_DEFINES})"
# The UF2 is written by the ELF's post-link step, so an up-to-date build
# ("no work to do") keeps the existing UF2. Only a missing UF2 forces a relink.
ELF_PATH="$BUILD_DIR/$BUILD_TARGET.elf"
[[ -f "$UF2_PATH" ]] || rm -f "$ELF_PATH"
"$CMAKE_BIN" "${CONFIGURE_ARGS[@]}"
"$CMAKE_BIN" --build "$BUILD_DIR" --target "$BUILD_TARGET" --parallel "$JOBS"
[[ -f "$UF2_PATH" ]] || die "build produced no $UF2_PATH"
[[ ! "$ELF_PATH" -nt "$UF2_PATH" ]] || die "$UF2_PATH is older than $ELF_PATH"

echo "✅ Build complete: $UF2_PATH"
