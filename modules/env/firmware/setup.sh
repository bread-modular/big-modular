#!/usr/bin/env bash
#
# setup.sh — one-time setup for compiling & flashing this ATtiny1616 firmware
# WITHOUT PlatformIO or VSCode. Uses arduino-cli + megaTinyCore.
#
# Safe to re-run. No Homebrew required.
#
set -euo pipefail

BIN_DIR="$HOME/bin"
ARDUINO_CLI="$BIN_DIR/arduino-cli"
INDEX_URL="http://drazzy.com/package_drazzy.com_index.json"
CORE_ID="megaTinyCore:megaavr"

# --- 0. OS packages (azero): nothing to install --------------------------------
# /usr/bin/arduino-cli with megaTinyCore 2.6.11 in the read-only data dir
# /opt/big-modular/arduino15 (the compile / flash scripts use it, see
# opt/attiny1616-tools/common.sh). `core install` into it fails on purpose, so
# only check. BIG_MODULAR_TOOLCHAINS=home runs the home setup below instead.
OS_ARDUINO_DATA=/opt/big-modular/arduino15
if [[ "${BIG_MODULAR_TOOLCHAINS:-}" != home && -d "$OS_ARDUINO_DATA" ]]; then
  if [[ -x /usr/bin/arduino-cli && \
        -f "$OS_ARDUINO_DATA/packages/megaTinyCore/hardware/megaavr/2.6.11/boards.txt" ]]; then
    echo "==> OS packages: $(ARDUINO_UPDATER_ENABLE_NOTIFICATION=false /usr/bin/arduino-cli version | head -1)"
    echo "==> OS packages: megaTinyCore:megaavr 2.6.11 in $OS_ARDUINO_DATA"
    echo "✅ Nothing to do (nothing downloaded or changed)."
    exit 0
  fi
  echo "arduino-cli or megaTinyCore 2.6.11 missing from the OS packages: install the azero" >&2
  echo "firmware-toolchains packages, or run BIG_MODULAR_TOOLCHAINS=home $0" >&2
  exit 1
fi

echo "==> Ensuring ~/bin is on PATH"
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
  export PATH="$BIN_DIR:$PATH"
fi

# --- 1. Install arduino-cli (standalone binary, no brew) ---------------------
if [[ -x "$ARDUINO_CLI" ]]; then
  echo "==> arduino-cli already installed: $("$ARDUINO_CLI" version | head -1)"
else
  echo "==> Downloading arduino-cli..."
  mkdir -p "$BIN_DIR"
  ARCH="$(uname -m)"
  case "$ARCH" in
    arm64)
      URL="https://downloads.arduino.cc/arduino-cli/arduino-cli_latest_macOS_ARM64.tar.gz"
      ;;
    x86_64)
      URL="https://downloads.arduino.cc/arduino-cli/arduino-cli_latest_macOS_64bit.tar.gz"
      ;;
    *)
      echo "Unsupported architecture: $ARCH" >&2
      exit 1
      ;;
  esac
  curl -fsSL "$URL" -o "$BIN_DIR/arduino-cli.tar.gz"
  tar xzf "$BIN_DIR/arduino-cli.tar.gz" -C "$BIN_DIR" arduino-cli
  chmod +x "$ARDUINO_CLI"
  rm -f "$BIN_DIR/arduino-cli.tar.gz"
  echo "==> Installed: $("$ARDUINO_CLI" version | head -1)"
fi

# --- 2. Persist ~/bin on PATH (zsh + bash) -----------------------------------
for rc in "$HOME/.zshrc" "$HOME/.bash_profile"; do
  if ! grep -q 'export PATH="$HOME/bin:$PATH"' "$rc" 2>/dev/null; then
    {
      echo ''
      echo '# arduino-cli (added by setup.sh)'
      echo 'export PATH="$HOME/bin:$PATH"'
    } >> "$rc"
    echo "==> Added ~/bin to PATH in $rc"
  fi
done

# --- 3. Register the megaTinyCore board index --------------------------------
CONFIG_FILE="$HOME/Library/Arduino15/arduino-cli.yaml"
if [[ -f "$CONFIG_FILE" ]] && grep -q 'drazzy.com' "$CONFIG_FILE" 2>/dev/null; then
  echo "==> megaTinyCore index already configured"
else
  echo "==> Registering megaTinyCore board index ($INDEX_URL)"
  "$ARDUINO_CLI" config add board_manager.additional_urls "$INDEX_URL"
fi

# --- 4. Install the megaTinyCore board package -------------------------------
echo "==> Updating board index..."
"$ARDUINO_CLI" core update-index

if "$ARDUINO_CLI" core list | grep -q '^megaTinyCore:megaavr'; then
  echo "==> megaTinyCore already installed"
else
  echo "==> Installing $CORE_ID (this downloads avr-gcc + avrdude, ~60 MB)..."
  "$ARDUINO_CLI" core install "$CORE_ID"
fi

echo ""
echo "✅ Setup complete."
echo "   Next: ./compile.sh   (build)"
echo "         ./flash.sh     (upload via UPDI)"
