#!/usr/bin/env bash
# common.sh — shared helpers for the RP2350 (Pico SDK) firmware scripts
# (sourced, not run).
#
# Module wrappers point the scripts at their Pico SDK project and add CMake
# defines through the environment, as with opt/esp32-tools:
#   RP2350_PROJECT_ROOT  CMake project dir (CMakeLists.txt + pico_sdk_import.cmake)
#   RP2350_DEFINES       space-separated KEY=VALUE, passed as cmake -DKEY=VALUE
#   RP2350_TARGET        CMake target / output name (default: project dir name)
#   RP2350_BUILD_DIR     build dir (default: $RP2350_PROJECT_ROOT/.build)
#
# Tools are looked up, never downloaded, here. The default home is Bread
# Modular's ~/.breadmodular, so an existing BM install is reused as is;
# ~/.pico-sdk (VS Code Pico extension) and the PATH are fallbacks.

PICO_SDK_VERSION="${PICO_SDK_VERSION:-2.1.1}"
TOOLCHAIN_VERSION="${TOOLCHAIN_VERSION:-14_2_Rel1}"
TOOLCHAIN_GNU_VERSION="${TOOLCHAIN_GNU_VERSION:-14.2.rel1}"
PICOTOOL_VERSION="${PICOTOOL_VERSION:-2.2.0-a4}"
BREADMODULAR_HOME="${BREADMODULAR_HOME:-$HOME/.breadmodular}"
VSCODE_PICO_HOME="$HOME/.pico-sdk"

die() {
  echo "Error: $*" >&2
  exit 1
}

# Pico SDK with the tinyusb submodule (USB serial): $PICO_SDK_PATH ->
# ~/.breadmodular/pico-sdk/sdk/<v> -> ~/.pico-sdk/sdk/<v>.
find_sdk() {
  local candidate
  for candidate in "${PICO_SDK_PATH:-}" "$BREADMODULAR_HOME/pico-sdk/sdk/$PICO_SDK_VERSION" \
                   "$VSCODE_PICO_HOME/sdk/$PICO_SDK_VERSION"; do
    if [[ -n "$candidate" && -f "$candidate/pico_sdk_init.cmake" && \
          -f "$candidate/lib/tinyusb/src/tusb.h" ]]; then
      echo "$candidate"
      return 0
    fi
  done
  return 1
}

# ARM GNU toolchain root (has bin/arm-none-eabi-gcc).
find_toolchain() {
  local candidate gcc
  for candidate in "${PICO_TOOLCHAIN_PATH:-}" "$BREADMODULAR_HOME/toolchain/$TOOLCHAIN_VERSION" \
                   "$VSCODE_PICO_HOME/toolchain/$TOOLCHAIN_VERSION"; do
    if [[ -n "$candidate" && -x "$candidate/bin/arm-none-eabi-gcc" ]]; then
      echo "$candidate"
      return 0
    fi
  done
  gcc="$(command -v arm-none-eabi-gcc 2>/dev/null)" || return 1
  dirname "$(dirname "$(readlink -f "$gcc")")"
}

find_picotool() {
  local candidate
  for candidate in "${PICOTOOL_BIN:-}" "$BREADMODULAR_HOME/picotool/$PICOTOOL_VERSION/picotool/picotool" \
                   "$VSCODE_PICO_HOME"/picotool/*/picotool/picotool; do
    if [[ -n "$candidate" && -x "$candidate" ]]; then
      echo "$candidate"
      return 0
    fi
  done
  command -v picotool 2>/dev/null
}

# cmake >= 3.13 (Pico SDK minimum): $CMAKE_BIN -> PATH -> ~/.breadmodular/bin.
find_cmake() {
  local candidate version
  for candidate in "${CMAKE_BIN:-}" "$(command -v cmake 2>/dev/null)" "$BREADMODULAR_HOME/bin/cmake"; do
    [[ -n "$candidate" && -x "$candidate" ]] || continue
    version="$("$candidate" --version 2>/dev/null | sed -n 's/^cmake version \([0-9]*\)\.\([0-9]*\).*/\1 \2/p')"
    read -r major minor <<< "$version"
    if [[ -n "${major:-}" ]] && (( major > 3 || (major == 3 && minor >= 13) )); then
      echo "$candidate"
      return 0
    fi
  done
  return 1
}

find_ninja() {
  local candidate
  for candidate in "${NINJA_BIN:-}" "$(command -v ninja 2>/dev/null)" "$BREADMODULAR_HOME/bin/ninja"; do
    if [[ -n "$candidate" && -x "$candidate" ]]; then
      echo "$candidate"
      return 0
    fi
  done
  return 1
}

# Resolve everything a build needs into PICO_SDK_PATH / PICO_TOOLCHAIN_PATH /
# CMAKE_BIN / NINJA_BIN / PICOTOOL_BIN (no downloads).
activate_pico() {
  PICO_SDK_PATH="$(find_sdk)" || die "Pico SDK $PICO_SDK_VERSION not found. Run ./setup.sh first."
  PICO_TOOLCHAIN_PATH="$(find_toolchain)" || die "arm-none-eabi-gcc not found. Run ./setup.sh first."
  CMAKE_BIN="$(find_cmake)" || die "cmake >= 3.13 not found. Run ./setup.sh first."
  NINJA_BIN="$(find_ninja || true)"
  PICOTOOL_BIN="$(find_picotool || true)"
  export PICO_SDK_PATH PICO_TOOLCHAIN_PATH
  export PATH="$PICO_TOOLCHAIN_PATH/bin:$PATH"
}

# Resolve the project into PROJECT_DIR / BUILD_DIR / BUILD_TARGET / CMAKE_DEFINE_ARGS.
resolve_project() {
  PROJECT_DIR="${RP2350_PROJECT_ROOT:-}"
  [[ -n "$PROJECT_DIR" && -f "$PROJECT_DIR/CMakeLists.txt" ]] || \
    die "RP2350_PROJECT_ROOT is not a CMake project: '${PROJECT_DIR}'"
  BUILD_DIR="${RP2350_BUILD_DIR:-$PROJECT_DIR/.build}"
  BUILD_TARGET="${RP2350_TARGET:-$(basename "$PROJECT_DIR")}"
  UF2_PATH="$BUILD_DIR/$BUILD_TARGET.uf2"
  CMAKE_DEFINE_ARGS=()
  local def
  for def in ${RP2350_DEFINES:-}; do
    CMAKE_DEFINE_ARGS+=("-D$def")
  done
}
