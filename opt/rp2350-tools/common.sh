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
# Tools are looked up, never downloaded, here.
#
# Where the tools come from (BIG_MODULAR_TOOLCHAINS):
#   os    the OS packages (azero): Pico SDK and picotool from
#         $BREADMODULAR_HOME = /opt/big-modular/rp2350, arm-none-eabi-gcc (Arch,
#         GCC 16.2), cmake and ninja from /usr/bin, by explicit path (a home
#         copy earlier on the PATH is never picked). Default where
#         /opt/big-modular/rp2350 exists.
#   home  as before: Bread Modular's ~/.breadmodular, so an existing BM install
#         is reused as is; ~/.pico-sdk (VS Code Pico extension) and the PATH
#         are fallbacks. Values under /opt/big-modular (from /etc/profile.d)
#         are ignored. Default where /opt/big-modular/rp2350 does not exist.
# Explicit tool variables (PICO_SDK_PATH, PICO_TOOLCHAIN_PATH, PICOTOOL_BIN,
# CMAKE_BIN, NINJA_BIN) win in both.

PICO_SDK_VERSION="${PICO_SDK_VERSION:-2.1.1}"
# The ARM GNU toolchain of the home lookup / setup.sh download (os: Arch's).
TOOLCHAIN_VERSION="${TOOLCHAIN_VERSION:-14_2_Rel1}"
TOOLCHAIN_GNU_VERSION="${TOOLCHAIN_GNU_VERSION:-14.2.rel1}"
PICOTOOL_VERSION="${PICOTOOL_VERSION:-2.2.0-a4}"
RP2350_OS_HOME=/opt/big-modular/rp2350
case "${BIG_MODULAR_TOOLCHAINS:-}" in
  home) RP2350_TOOLCHAINS=home ;;
  os) RP2350_TOOLCHAINS=os ;;
  "") if [[ -d "$RP2350_OS_HOME" ]]; then RP2350_TOOLCHAINS=os; else RP2350_TOOLCHAINS=home; fi ;;
  *) echo "Error: BIG_MODULAR_TOOLCHAINS must be 'os' or 'home', not '$BIG_MODULAR_TOOLCHAINS'" >&2; exit 1 ;;
esac
if [[ "$RP2350_TOOLCHAINS" == os ]]; then
  BREADMODULAR_HOME="${BREADMODULAR_HOME:-$RP2350_OS_HOME}"
else
  [[ "${BREADMODULAR_HOME:-}" != /opt/big-modular/* ]] || unset BREADMODULAR_HOME
  BREADMODULAR_HOME="${BREADMODULAR_HOME:-$HOME/.breadmodular}"
fi
VSCODE_PICO_HOME="$HOME/.pico-sdk"

die() {
  echo "Error: $*" >&2
  exit 1
}

# Pico SDK with the tinyusb submodule (USB serial): $PICO_SDK_PATH ->
# $BREADMODULAR_HOME/pico-sdk/sdk/<v> -> ~/.pico-sdk/sdk/<v> (home only).
find_sdk() {
  local candidate vscode=()
  [[ "$RP2350_TOOLCHAINS" == os ]] || vscode=("$VSCODE_PICO_HOME/sdk/$PICO_SDK_VERSION")
  for candidate in "${PICO_SDK_PATH:-}" "$BREADMODULAR_HOME/pico-sdk/sdk/$PICO_SDK_VERSION" \
                   "${vscode[@]+"${vscode[@]}"}"; do
    if [[ -n "$candidate" && -f "$candidate/pico_sdk_init.cmake" && \
          -f "$candidate/lib/tinyusb/src/tusb.h" ]]; then
      echo "$candidate"
      return 0
    fi
  done
  return 1
}

# ARM GNU toolchain root (has bin/arm-none-eabi-gcc): $PICO_TOOLCHAIN_PATH ->
# os: /usr; home: ~/.breadmodular/toolchain/<v> -> ~/.pico-sdk/toolchain/<v> -> PATH.
find_toolchain() {
  local candidate gcc
  if [[ "$RP2350_TOOLCHAINS" == os ]]; then
    for candidate in "${PICO_TOOLCHAIN_PATH:-}" /usr; do
      if [[ -n "$candidate" && -x "$candidate/bin/arm-none-eabi-gcc" ]]; then
        echo "$candidate"
        return 0
      fi
    done
    return 1
  fi
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

# picotool: $PICOTOOL_BIN -> $BREADMODULAR_HOME/picotool/<v> -> home only:
# ~/.pico-sdk/picotool/* -> PATH.
find_picotool() {
  local candidate vscode=()
  [[ "$RP2350_TOOLCHAINS" == os ]] || vscode=("$VSCODE_PICO_HOME"/picotool/*/picotool/picotool)
  for candidate in "${PICOTOOL_BIN:-}" "$BREADMODULAR_HOME/picotool/$PICOTOOL_VERSION/picotool/picotool" \
                   "${vscode[@]+"${vscode[@]}"}"; do
    if [[ -n "$candidate" && -x "$candidate" ]]; then
      echo "$candidate"
      return 0
    fi
  done
  [[ "$RP2350_TOOLCHAINS" == home ]] || return 1
  command -v picotool 2>/dev/null
}

# cmake >= 3.13 (Pico SDK minimum): $CMAKE_BIN -> os: /usr/bin/cmake;
# home: PATH -> ~/.breadmodular/bin.
find_cmake() {
  local candidate version list=()
  if [[ "$RP2350_TOOLCHAINS" == os ]]; then
    list=("${CMAKE_BIN:-}" /usr/bin/cmake)
  else
    list=("${CMAKE_BIN:-}" "$(command -v cmake 2>/dev/null)" "$BREADMODULAR_HOME/bin/cmake")
  fi
  for candidate in "${list[@]}"; do
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

# ninja: $NINJA_BIN -> os: /usr/bin/ninja; home: PATH -> ~/.breadmodular/bin.
find_ninja() {
  local candidate list=()
  if [[ "$RP2350_TOOLCHAINS" == os ]]; then
    list=("${NINJA_BIN:-}" /usr/bin/ninja)
  else
    list=("${NINJA_BIN:-}" "$(command -v ninja 2>/dev/null)" "$BREADMODULAR_HOME/bin/ninja")
  fi
  for candidate in "${list[@]}"; do
    if [[ -n "$candidate" && -x "$candidate" ]]; then
      echo "$candidate"
      return 0
    fi
  done
  return 1
}

# Extra hint for a "not found" in os mode.
os_hint() {
  [[ "$RP2350_TOOLCHAINS" == os ]] || return 0
  printf '%s' " (OS toolchains: install the azero firmware-toolchains packages, or BIG_MODULAR_TOOLCHAINS=home)"
}

# Pico SDK version: git tag, else pico_sdk_version.cmake (release archives, the
# OS package), else "unknown".
sdk_version() {
  local v
  if [[ -e "$1/.git" ]] && v="$(git -C "$1" describe --tags 2>/dev/null)"; then
    echo "$v"
    return 0
  fi
  v="$(sed -n 's/^set(PICO_SDK_VERSION_\(MAJOR\|MINOR\|REVISION\) \([0-9]*\))$/\2/p' \
         "$1/pico_sdk_version.cmake" 2>/dev/null | paste -sd. -)"
  echo "${v:-unknown}"
}

# Resolve everything a build needs into PICO_SDK_PATH / PICO_TOOLCHAIN_PATH /
# CMAKE_BIN / NINJA_BIN / PICOTOOL_BIN (no downloads).
activate_pico() {
  PICO_SDK_PATH="$(find_sdk)" || die "Pico SDK $PICO_SDK_VERSION not found. Run ./setup.sh first.$(os_hint)"
  PICO_TOOLCHAIN_PATH="$(find_toolchain)" || die "arm-none-eabi-gcc not found. Run ./setup.sh first.$(os_hint)"
  CMAKE_BIN="$(find_cmake)" || die "cmake >= 3.13 not found. Run ./setup.sh first.$(os_hint)"
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
