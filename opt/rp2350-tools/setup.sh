#!/usr/bin/env bash
# setup.sh — one-time Pico SDK setup for the RP2350 firmwares.
#
# Reuses what is already installed (see common.sh: ~/.breadmodular from the
# Bread Modular scripts, ~/.pico-sdk from the VS Code Pico extension, the
# PATH) and only checks it. Missing pieces get the Bread Modular install, in
# the Bread Modular layout under $BREADMODULAR_HOME (~/.breadmodular), for
# Linux and macOS:
#
#   Pico SDK 2.1.1 (+ lib/tinyusb)   pico-sdk/sdk/2.1.1
#   ARM GNU toolchain 14.2.rel1      toolchain/14_2_Rel1
#   picotool 2.2.0-a4                picotool/2.2.0-a4/picotool
#   cmake, ninja (only if not on the PATH)   cmake/, bin/
#
# Safe to re-run; downloads are cached in $BREADMODULAR_HOME/downloads.
set -euo pipefail

TOOLS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$TOOLS_DIR/common.sh"

PICO_SDK_REPO="${PICO_SDK_REPO:-https://github.com/raspberrypi/pico-sdk.git}"
PICOTOOL_RELEASE="${PICOTOOL_RELEASE:-v2.2.0-3}"
CMAKE_VERSION="${CMAKE_VERSION:-4.3.3}"
NINJA_VERSION="${NINJA_VERSION:-1.12.1}"
DOWNLOADS="$BREADMODULAR_HOME/downloads"

OS="$(uname -s)"
ARCH="$(uname -m)"
case "$OS/$ARCH" in
  Linux/x86_64)         TC_HOST=x86_64;        PT_HOST=x86_64-lin;  CM_HOST=linux-x86_64;    NJ_ZIP=ninja-linux.zip ;;
  Linux/aarch64)        TC_HOST=aarch64;       PT_HOST=aarch64-lin; CM_HOST=linux-aarch64;   NJ_ZIP=ninja-linux-aarch64.zip ;;
  Darwin/arm64)         TC_HOST=darwin-arm64;  PT_HOST=mac;         CM_HOST=macos-universal; NJ_ZIP=ninja-mac.zip ;;
  Darwin/x86_64)        TC_HOST=darwin-x86_64; PT_HOST=mac;         CM_HOST=macos-universal; NJ_ZIP=ninja-mac.zip ;;
  *) die "unsupported host $OS/$ARCH (Linux x86_64/aarch64, macOS)" ;;
esac

need() {
  command -v "$1" >/dev/null 2>&1 || die "missing required tool: $1"
}

# fetch <url> -> prints the cached archive path
fetch() {
  local url="$1" out="$DOWNLOADS/${1##*/}"
  mkdir -p "$DOWNLOADS"
  if [[ ! -f "$out" ]]; then
    echo "==> Downloading $url" >&2
    curl -fL --retry 3 --retry-delay 2 -o "$out.tmp" "$url"
    mv "$out.tmp" "$out"
  else
    echo "==> Using cached $out" >&2
  fi
  echo "$out"
}

unquarantine() {
  [[ "$OS" == Darwin ]] && xattr -dr com.apple.quarantine "$1" 2>/dev/null || true
}

need git
need curl
need tar
mkdir -p "$BREADMODULAR_HOME/bin"

# --- 1. Pico SDK -------------------------------------------------------------------
if SDK="$(find_sdk)"; then
  echo "==> Reusing Pico SDK at $SDK"
else
  SDK="$BREADMODULAR_HOME/pico-sdk/sdk/$PICO_SDK_VERSION"
  if [[ ! -d "$SDK/.git" ]]; then
    [[ -e "$SDK" ]] && die "$SDK exists but is not a git checkout; move it aside"
    echo "==> Cloning Pico SDK $PICO_SDK_VERSION into $SDK"
    mkdir -p "$(dirname "$SDK")"
    git clone --branch "$PICO_SDK_VERSION" --depth 1 "$PICO_SDK_REPO" "$SDK"
  fi
  # Only tinyusb (USB serial); btstack / cyw43 / lwip / mbedtls are not used.
  echo "==> Fetching SDK submodule lib/tinyusb"
  git -C "$SDK" submodule update --init --depth 1 -- lib/tinyusb
fi
FOUND_VERSION="$(git -C "$SDK" describe --tags 2>/dev/null || echo unknown)"
[[ "$FOUND_VERSION" == "$PICO_SDK_VERSION" ]] || \
  echo "Warning: Pico SDK is $FOUND_VERSION, the firmware is tested with $PICO_SDK_VERSION." >&2

# --- 2. ARM GNU toolchain ------------------------------------------------------------
if TC="$(find_toolchain)"; then
  echo "==> Reusing ARM toolchain at $TC"
else
  TC="$BREADMODULAR_HOME/toolchain/$TOOLCHAIN_VERSION"
  PKG="arm-gnu-toolchain-$TOOLCHAIN_GNU_VERSION-$TC_HOST-arm-none-eabi"
  ARCHIVE="$(fetch "https://developer.arm.com/-/media/Files/downloads/gnu/$TOOLCHAIN_GNU_VERSION/binrel/$PKG.tar.xz")"
  echo "==> Extracting the toolchain to $TC (~130 MB download, ~1 GB unpacked)"
  mkdir -p "$(dirname "$TC")"
  rm -rf "$TC" "$(dirname "$TC")/$PKG"
  tar -xf "$ARCHIVE" -C "$(dirname "$TC")"
  mv "$(dirname "$TC")/$PKG" "$TC"
  unquarantine "$TC"
  [[ -x "$TC/bin/arm-none-eabi-gcc" ]] || die "toolchain install failed: $TC"
fi

# --- 3. picotool -------------------------------------------------------------------
if PT="$(find_picotool)"; then
  echo "==> Reusing picotool at $PT"
else
  PT_DIR="$BREADMODULAR_HOME/picotool/$PICOTOOL_VERSION"
  URL="https://github.com/raspberrypi/pico-sdk-tools/releases/download/$PICOTOOL_RELEASE/picotool-$PICOTOOL_VERSION-$PT_HOST"
  mkdir -p "$PT_DIR"
  if [[ "$PT_HOST" == mac ]]; then
    need unzip
    unzip -qo "$(fetch "$URL.zip")" -d "$PT_DIR"
  else
    tar -xzf "$(fetch "$URL.tar.gz")" -C "$PT_DIR"
  fi
  PT="$PT_DIR/picotool/picotool"
  unquarantine "$PT_DIR"
  [[ -x "$PT" ]] || die "picotool install failed: $PT"
fi

# --- 4. cmake + ninja: only when the PATH has none -----------------------------------
if CM="$(find_cmake)"; then
  echo "==> Reusing $CM"
else
  PKG="cmake-$CMAKE_VERSION-$CM_HOST"
  ARCHIVE="$(fetch "https://github.com/Kitware/CMake/releases/download/v$CMAKE_VERSION/$PKG.tar.gz")"
  mkdir -p "$BREADMODULAR_HOME/cmake"
  rm -rf "$BREADMODULAR_HOME/cmake/$PKG"
  tar -xzf "$ARCHIVE" -C "$BREADMODULAR_HOME/cmake"
  unquarantine "$BREADMODULAR_HOME/cmake/$PKG"
  CM_BIN_DIR="$BREADMODULAR_HOME/cmake/$PKG/bin"
  [[ "$OS" == Darwin ]] && CM_BIN_DIR="$BREADMODULAR_HOME/cmake/$PKG/CMake.app/Contents/bin"
  for t in cmake ctest cpack; do ln -sf "$CM_BIN_DIR/$t" "$BREADMODULAR_HOME/bin/$t"; done
  CM="$BREADMODULAR_HOME/bin/cmake"
fi
if NJ="$(find_ninja)"; then
  echo "==> Reusing $NJ"
else
  need unzip
  unzip -qo "$(fetch "https://github.com/ninja-build/ninja/releases/download/v$NINJA_VERSION/$NJ_ZIP")" \
    -d "$BREADMODULAR_HOME/bin"
  NJ="$BREADMODULAR_HOME/bin/ninja"
  unquarantine "$NJ"
fi

# --- 5. Report -----------------------------------------------------------------------
echo "==> Pico SDK $FOUND_VERSION: $SDK"
echo "==> $("$TC/bin/arm-none-eabi-gcc" --version | head -1)"
echo "==> $("$PT" version 2>/dev/null | head -1)"
echo "==> $("$CM" --version | head -1), ninja $("$NJ" --version)"

# --- 6. USB access for picotool (Linux) ------------------------------------------------
if [[ "$OS" == Linux ]] && ! grep -rqs '2e8a' /etc/udev/rules.d /lib/udev/rules.d /usr/lib/udev/rules.d; then
  echo "Note: no udev rule for Raspberry Pi USB devices (2e8a); picotool needs root without one." >&2
  echo "  See opt/rp2350-tools/README.md (99-picotool.rules), or flash via the RP2350 drive." >&2
fi

echo ""
echo "✅ Setup complete. Next: ./compile.sh  /  ./flash.sh"
