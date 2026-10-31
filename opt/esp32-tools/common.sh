#!/usr/bin/env bash
# common.sh — shared helpers for the ESP32-S3 firmware scripts (sourced, not run).
#
# Module wrappers point the scripts at their ESP-IDF project and add CMake
# defines through the environment, as with opt/attiny1616-tools:
#   ESP32_PROJECT_ROOT  ESP-IDF project dir (has CMakeLists.txt + main/)
#   ESP32_DEFINES       space-separated KEY=VALUE, passed as idf.py -D KEY=VALUE

IDF_VERSION="${IDF_VERSION:-v5.5.1}"
IDF_TARGET="${IDF_TARGET:-esp32s3}"

die() {
  echo "Error: $*" >&2
  exit 1
}

# Locate ESP-IDF: $IDF_PATH -> $IDF_DIR -> ~/esp/esp-idf -> ~/esp/esp-idf-<version>.
find_idf() {
  local candidate
  for candidate in "${IDF_PATH:-}" "${IDF_DIR:-}" "$HOME/esp/esp-idf" \
                   "$HOME/esp/esp-idf-$IDF_VERSION"; do
    if [[ -n "$candidate" && -f "$candidate/export.sh" ]]; then
      echo "$candidate"
      return 0
    fi
  done
  return 1
}

# Source the ESP-IDF environment into the current shell (no downloads).
activate_idf() {
  local idf_dir
  idf_dir="$(find_idf)" || die "ESP-IDF not found. Run ./setup.sh first."
  # export.sh reads positional args; clear them for the sourced script.
  set --
  # shellcheck source=/dev/null
  source "$idf_dir/export.sh" >/dev/null || \
    die "ESP-IDF at $idf_dir did not activate. Run ./setup.sh."
  export IDF_TARGET
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
