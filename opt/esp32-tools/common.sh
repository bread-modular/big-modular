#!/usr/bin/env bash
# common.sh — shared helpers for the ESP32-S3 firmware scripts (sourced, not run).
#
# Module wrappers point the scripts at their ESP-IDF project and add CMake
# defines through the environment, as with opt/attiny1616-tools:
#   ESP32_PROJECT_ROOT  ESP-IDF project dir (has CMakeLists.txt + main/)
#   ESP32_DEFINES       space-separated KEY=VALUE, passed as idf.py -D KEY=VALUE

#
# Where ESP-IDF comes from (BIG_MODULAR_TOOLCHAINS):
#   os    the OS packages (azero): IDF_PATH /opt/big-modular/esp32/esp-idf with
#         its tools in IDF_TOOLS_PATH /opt/big-modular/esp32/espressif, /usr/bin
#         first on the PATH (Arch's cmake / ninja / python3, never a home copy).
#         Default where /opt/big-modular/esp32 exists.
#   home  as before: ~/esp/esp-idf with ~/.espressif. IDF_PATH / IDF_TOOLS_PATH
#         under /opt/big-modular (from /etc/profile.d) are ignored. Default where
#         /opt/big-modular/esp32 does not exist.
# An explicit IDF_PATH / IDF_DIR (outside /opt/big-modular) wins in both.

IDF_VERSION="${IDF_VERSION:-v5.5.1}"
IDF_TARGET="${IDF_TARGET:-esp32s3}"
ESP32_OS_HOME=/opt/big-modular/esp32
case "${BIG_MODULAR_TOOLCHAINS:-}" in
  home) ESP32_TOOLCHAINS=home ;;
  os) ESP32_TOOLCHAINS=os ;;
  "") if [[ -d "$ESP32_OS_HOME" ]]; then ESP32_TOOLCHAINS=os; else ESP32_TOOLCHAINS=home; fi ;;
  *) echo "Error: BIG_MODULAR_TOOLCHAINS must be 'os' or 'home', not '$BIG_MODULAR_TOOLCHAINS'" >&2; exit 1 ;;
esac
if [[ "$ESP32_TOOLCHAINS" == home ]]; then
  [[ "${IDF_PATH:-}" != /opt/big-modular/* ]] || unset IDF_PATH
  [[ "${IDF_TOOLS_PATH:-}" != /opt/big-modular/* ]] || unset IDF_TOOLS_PATH
fi

die() {
  echo "Error: $*" >&2
  exit 1
}

# shellcheck source=../build-dir.sh
source "$(dirname "${BASH_SOURCE[0]}")/../build-dir.sh"

# Locate ESP-IDF: $IDF_PATH -> $IDF_DIR -> os: /opt/big-modular/esp32/esp-idf;
# home: ~/esp/esp-idf -> ~/esp/esp-idf-<version>.
find_idf() {
  local candidate list=("${IDF_PATH:-}" "${IDF_DIR:-}")
  if [[ "$ESP32_TOOLCHAINS" == os ]]; then
    list+=("$ESP32_OS_HOME/esp-idf")
  else
    list+=("$HOME/esp/esp-idf" "$HOME/esp/esp-idf-$IDF_VERSION")
  fi
  for candidate in "${list[@]}"; do
    if [[ -n "$candidate" && -f "$candidate/export.sh" ]]; then
      echo "$candidate"
      return 0
    fi
  done
  return 1
}

# Environment for sourcing <idf>/export.sh: the OS-packaged IDF gets its
# packaged tools (IDF_TOOLS_PATH) and /usr/bin ahead of the home dirs on PATH.
idf_tools_env() { # idf_dir
  if [[ "$1" == "$ESP32_OS_HOME/esp-idf" ]]; then
    export IDF_TOOLS_PATH="${IDF_TOOLS_PATH:-$ESP32_OS_HOME/espressif}"
  fi
  if [[ "$ESP32_TOOLCHAINS" == os ]]; then
    export PATH="/usr/bin:$PATH"
  fi
}

# Extra hint for a "not found" in os mode.
os_hint() {
  [[ "$ESP32_TOOLCHAINS" == os ]] || return 0
  printf '%s' " (OS toolchains: install the azero firmware-toolchains packages, or BIG_MODULAR_TOOLCHAINS=home)"
}

# ESP-IDF version: git tag, else version.txt (release zip, the OS package).
idf_version() {
  local v
  if [[ -e "$1/.git" ]] && v="$(git -C "$1" describe --tags 2>/dev/null)"; then
    echo "$v"
  elif [[ -s "$1/version.txt" ]]; then
    head -1 "$1/version.txt"
  else
    echo unknown
  fi
}

# Source the ESP-IDF environment into the current shell (no downloads).
activate_idf() {
  local idf_dir
  idf_dir="$(find_idf)" || die "ESP-IDF not found. Run ./setup.sh first.$(os_hint)"
  idf_tools_env "$idf_dir"
  echo "==> ESP-IDF $idf_dir (tools: ${IDF_TOOLS_PATH:-$HOME/.espressif}, $ESP32_TOOLCHAINS toolchains)"
  # export.sh reads positional args; clear them for the sourced script.
  set --
  # shellcheck source=/dev/null
  source "$idf_dir/export.sh" >/dev/null || \
    die "ESP-IDF at $idf_dir did not activate. Run ./setup.sh."
  export IDF_TARGET
}

# Remove an idf.py build dir (default <project>/build) configured with another
# ESP-IDF, Python environment, toolchain, cmake or ninja (BIG_MODULAR_TOOLCHAINS
# os vs home, a moved install or checkout), one line with the reason: idf.py
# would stop at "... Run 'idf.py fullclean' to start again." or build with the
# cached tools. Call after activate_idf.
check_idf_build_dir() { # project_dir [build_dir]
  local proj="$1" build="${2:-$1/build}" cache ar gcc
  cache="$build/CMakeCache.txt"
  [[ -f "$cache" ]] || return 0
  cmake_cache_expect "$cache" CMAKE_HOME_DIRECTORY "$proj" path
  cmake_cache_expect "$cache" CMAKE_CACHEFILE_DIR "$build" path
  cmake_cache_expect "$cache" esp-idf_SOURCE_DIR "$IDF_PATH" path
  cmake_cache_expect "$cache" CMAKE_TOOLCHAIN_FILE "$IDF_PATH/tools/cmake/toolchain-$IDF_TARGET.cmake" path
  cmake_cache_expect "$cache" IDF_TARGET "$IDF_TARGET"
  # idf.py compares the plain strings (its own fullclean check).
  cmake_cache_expect "$cache" PYTHON "$(python -c 'import sys; print(sys.executable)')"
  if ar="$(cmake_cache_value "$cache" CMAKE_AR)" && [[ -n "$ar" ]]; then
    gcc="$(basename "$ar")"
    gcc="$(command -v "${gcc%-ar}-gcc" || echo "(no ${gcc%-ar}-gcc)")"
    cmake_cache_expect "$cache" CMAKE_AR "$(dirname "$gcc")/$(basename "$ar")" path
  fi
  if [[ "$(cmake_cache_value "$cache" CMAKE_GENERATOR || true)" == Ninja ]]; then
    cmake_cache_expect "$cache" CMAKE_MAKE_PROGRAM "$(command -v ninja || echo '(no ninja)')" path
  fi
  cmake_cache_expect "$cache" CMAKE_COMMAND "$(command -v cmake || echo '(no cmake)')" path
  remove_build_dir_if_stale "$build" "$proj"
}

# Resolve the project dir and the idf.py -D arguments into PROJECT_DIR / IDF_DEFINE_ARGS.
resolve_project() {
  PROJECT_DIR="${ESP32_PROJECT_ROOT:-}"
  [[ -n "$PROJECT_DIR" && -f "$PROJECT_DIR/CMakeLists.txt" ]] || \
    die "ESP32_PROJECT_ROOT is not an ESP-IDF project: '${PROJECT_DIR}'"
  IDF_DEFINE_ARGS=()
  local def
  for def in ${ESP32_DEFINES:-}; do
    IDF_DEFINE_ARGS+=(-D "$def")
  done
}
