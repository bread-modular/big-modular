#!/usr/bin/env bash
# compile.sh — configure + build an RP2350 Pico SDK project (see common.sh for
# the env). Output: $RP2350_BUILD_DIR/<target>.uf2 (and .elf / .bin / .hex).
set -euo pipefail

TOOLS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../checkout-owner.sh
source "$TOOLS_DIR/../checkout-owner.sh"
require_checkout_owner "$@"
# shellcheck source=common.sh
source "$TOOLS_DIR/common.sh"
# shellcheck source=../build-dir.sh
source "$TOOLS_DIR/../build-dir.sh"

resolve_project
activate_pico

if [[ -n "$NINJA_BIN" ]]; then
  GENERATOR=(-G Ninja -DCMAKE_MAKE_PROGRAM="$NINJA_BIN")
else
  GENERATOR=(-G "Unix Makefiles")
fi

# A build dir configured with other tools (BIG_MODULAR_TOOLCHAINS os vs home, a
# moved SDK / toolchain / checkout) is removed first: CMake keeps a cached
# compiler, so reusing it mixes two toolchains or stops at "is not a
# subdirectory of" the new SDK. APP_NAME / defines changes reconfigure in place.
CACHE="$BUILD_DIR/CMakeCache.txt"
if [[ -f "$CACHE" ]]; then
  cmake_cache_expect "$CACHE" CMAKE_HOME_DIRECTORY "$PROJECT_DIR" path
  cmake_cache_expect "$CACHE" CMAKE_CACHEFILE_DIR "$BUILD_DIR" path
  cmake_cache_expect "$CACHE" PICO_SDK_PATH "$PICO_SDK_PATH" path
  cmake_cache_expect "$CACHE" PICO_TOOLCHAIN_PATH "$PICO_TOOLCHAIN_PATH" path
  cmake_cache_expect "$CACHE" CMAKE_C_COMPILER "$PICO_TOOLCHAIN_PATH/bin/arm-none-eabi-gcc" path
  cmake_cache_expect "$CACHE" CMAKE_CXX_COMPILER "$PICO_TOOLCHAIN_PATH/bin/arm-none-eabi-g++" path
  cmake_cache_expect "$CACHE" CMAKE_GENERATOR "${GENERATOR[1]}"
  [[ -z "$NINJA_BIN" ]] || cmake_cache_expect "$CACHE" CMAKE_MAKE_PROGRAM "$NINJA_BIN" path
  cmake_cache_expect "$CACHE" CMAKE_COMMAND "$CMAKE_BIN" path
  remove_build_dir_if_stale "$BUILD_DIR" "$PROJECT_DIR"
fi

CONFIGURE_ARGS=(-S "$PROJECT_DIR" -B "$BUILD_DIR" "${GENERATOR[@]}"
                -DPICO_SDK_PATH="$PICO_SDK_PATH" -DPICO_TOOLCHAIN_PATH="$PICO_TOOLCHAIN_PATH")
# Reuse the installed picotool; without the hint the SDK downloads and builds
# picotool from source on every fresh build dir.
if [[ -n "$PICOTOOL_BIN" && -f "$(dirname "$PICOTOOL_BIN")/picotoolConfig.cmake" ]]; then
  CONFIGURE_ARGS+=(-Dpicotool_DIR="$(dirname "$PICOTOOL_BIN")")
fi
CONFIGURE_ARGS+=("${CMAKE_DEFINE_ARGS[@]+"${CMAKE_DEFINE_ARGS[@]}"}")

JOBS="${JOBS:-$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)}"

echo "==> Pico SDK $PICO_SDK_PATH"
echo "==> Toolchain $PICO_TOOLCHAIN_PATH/bin/arm-none-eabi-gcc ($("$PICO_TOOLCHAIN_PATH/bin/arm-none-eabi-gcc" -dumpversion), $RP2350_TOOLCHAINS toolchains)"
echo "==> $CMAKE_BIN${NINJA_BIN:+, $NINJA_BIN}${PICOTOOL_BIN:+, $PICOTOOL_BIN}"
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
