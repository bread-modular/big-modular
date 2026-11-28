#!/usr/bin/env bash
# setup.sh — one-time ESP-IDF setup for the ESP32-S3 firmwares.
#
# Reuses an existing ESP-IDF + toolchain when one is already installed
# ($IDF_PATH, $IDF_DIR or ~/esp/esp-idf, with ~/.espressif tools): it only
# checks it, nothing is downloaded. Only a machine without ESP-IDF gets the
# Bread Modular install (clone $IDF_VERSION, install.sh esp32s3, cmake + ninja).
# With the OS packages (azero, see common.sh: BIG_MODULAR_TOOLCHAINS) it only
# checks them: nothing is downloaded or written.
#
# Safe to re-run.
set -euo pipefail

TOOLS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$TOOLS_DIR/common.sh"
# shellcheck source=../azero-os.sh
source "$TOOLS_DIR/../azero-os.sh"

IDF_REPO="https://github.com/espressif/esp-idf.git"

for cmd in git python3; do
  command -v "$cmd" >/dev/null 2>&1 || die "missing required tool: $cmd"
done

# --- 1. ESP-IDF source ---------------------------------------------------------
if IDF_FOUND="$(find_idf)"; then
  echo "==> Reusing ESP-IDF at $IDF_FOUND"
else
  [[ "$ESP32_TOOLCHAINS" != os ]] || die "ESP-IDF not found in the OS packages.$(os_hint)"
  IDF_FOUND="${IDF_DIR:-$HOME/esp/esp-idf}"
  echo "==> No ESP-IDF found. Cloning $IDF_VERSION into $IDF_FOUND (~1.5 GB) ..."
  git clone --recursive --branch "$IDF_VERSION" --depth 1 "$IDF_REPO" "$IDF_FOUND"
fi

FOUND_VERSION="$(idf_version "$IDF_FOUND")"
idf_tools_env "$IDF_FOUND"
if [[ "$FOUND_VERSION" != "$IDF_VERSION" ]]; then
  echo "Warning: ESP-IDF is $FOUND_VERSION, the firmware is tested with $IDF_VERSION." >&2
fi

# --- 2. Toolchain + Python env: install only if export.sh cannot activate --------
if (set --; source "$IDF_FOUND/export.sh" >/dev/null 2>&1 && \
    command -v xtensa-esp32s3-elf-gcc >/dev/null && command -v cmake >/dev/null && \
    command -v ninja >/dev/null); then
  echo "==> ESP-IDF tools already installed (${IDF_TOOLS_PATH:-~/.espressif}), nothing to download"
else
  [[ "$ESP32_TOOLCHAINS" != os ]] || die "ESP-IDF tools in ${IDF_TOOLS_PATH:-~/.espressif} do not activate.$(os_hint)"
  echo "==> Installing ESP-IDF tools for $IDF_TARGET ..."
  "$IDF_FOUND/install.sh" "$IDF_TARGET"
  # cmake/ninja are on_request tools on macOS/Linux.
  python3 "$IDF_FOUND/tools/idf_tools.py" install cmake ninja
fi

# --- 3. Report -------------------------------------------------------------------
(
  set --
  source "$IDF_FOUND/export.sh" >/dev/null 2>&1
  echo "==> $(idf.py --version 2>/dev/null)"
  echo "==> $(xtensa-esp32s3-elf-gcc --version | head -1)"
  echo "==> $(cmake --version | head -1), ninja $(ninja --version)"
)

# --- 4. Serial port access (Linux) -------------------------------------------------
if azero_os; then
  echo "==> Serial port access: provided by Azero OS (group uucp, udev rules), no group change"
elif [[ "$(uname -s)" == Linux ]] && ! id -nG | tr ' ' '\n' | grep -qx dialout; then
  echo "Note: add yourself to 'dialout' to flash without sudo:" >&2
  echo "  sudo usermod -aG dialout \"\$USER\"   (then log out and back in)" >&2
fi

echo ""
echo "✅ Setup complete. Next: ./compile.sh  /  ./flash.sh"
