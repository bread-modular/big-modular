#!/usr/bin/env bash
# common.sh — arduino-cli lookup for the ATtiny1616 compile / flash scripts
# (sourced, not run). Sets ARDUINO_CLI (the binary to run) and its environment.
#
# Where arduino-cli and megaTinyCore come from (BIG_MODULAR_TOOLCHAINS):
#   os    the OS packages (azero): /usr/bin/arduino-cli with the read-only data
#         dir /opt/big-modular/arduino15 (megaTinyCore 2.6.11 + its avr-gcc /
#         avrdude), by explicit path: ~/bin/arduino-cli and ~/.arduino15 are not
#         used. Default where /opt/big-modular/arduino15 exists.
#   home  as before: ~/bin first on the PATH, arduino-cli's own data dir
#         (~/.arduino15). ARDUINO_DIRECTORIES_* values from
#         /etc/profile.d/big-modular-arduino.sh are ignored. Default where
#         /opt/big-modular/arduino15 does not exist.
# ARDUINO_CLI_BIN overrides the arduino-cli binary in both.
#
# os: arduino-cli downloads library_index.json into its data dir at every start
# when the file is missing, and cannot save it in the read-only one ("Error
# saving downloaded index: ... permission denied", a 4.5 MB download each
# time). The sketches need no library-manager library, so the scripts run
# arduino-cli on a writable view of the packaged dir: $ARDUINO_OS_VIEW, links to
# the packaged files plus an empty library index and the board-index config.
# A data dir set to anything other than the packaged one is used as is.

ARDUINO_OS_DATA=/opt/big-modular/arduino15
ARDUINO_OS_VIEW="${XDG_CACHE_HOME:-$HOME/.cache}/big-modular/arduino15"
MEGATINYCORE_INDEX_URL="http://drazzy.com/package_drazzy.com_index.json"

case "${BIG_MODULAR_TOOLCHAINS:-}" in
  home) ATTINY_TOOLCHAINS=home ;;
  os) ATTINY_TOOLCHAINS=os ;;
  "") if [[ -d "$ARDUINO_OS_DATA" ]]; then ATTINY_TOOLCHAINS=os; else ATTINY_TOOLCHAINS=home; fi ;;
  *) echo "Error: BIG_MODULAR_TOOLCHAINS must be 'os' or 'home', not '$BIG_MODULAR_TOOLCHAINS'" >&2; exit 1 ;;
esac

# Writable view of the packaged data dir (see above); prints its path.
arduino_os_view() {
  local f
  mkdir -p "$ARDUINO_OS_VIEW" || return 1
  for f in "$ARDUINO_OS_DATA"/*; do
    case "${f##*/}" in
      library_index.json*|arduino-cli.yaml) continue ;;
    esac
    ln -sfn "$f" "$ARDUINO_OS_VIEW/${f##*/}" || return 1
  done
  [[ -f "$ARDUINO_OS_VIEW/library_index.json" ]] || \
    echo '{"libraries":[]}' > "$ARDUINO_OS_VIEW/library_index.json" || return 1
  printf 'board_manager:\n  additional_urls:\n    - %s\n' "$MEGATINYCORE_INDEX_URL" \
    > "$ARDUINO_OS_VIEW/arduino-cli.yaml" || return 1
  echo "$ARDUINO_OS_VIEW"
}

if [[ "$ATTINY_TOOLCHAINS" == os ]]; then
  ARDUINO_CLI="${ARDUINO_CLI_BIN:-/usr/bin/arduino-cli}"
  if [[ -z "${ARDUINO_DIRECTORIES_DATA:-}" || "$ARDUINO_DIRECTORIES_DATA" == "$ARDUINO_OS_DATA" ]]; then
    if view="$(arduino_os_view)"; then
      export ARDUINO_DIRECTORIES_DATA="$view"
      export ARDUINO_CONFIG_FILE="$view/arduino-cli.yaml"
    else
      echo "Warning: no writable view in $ARDUINO_OS_VIEW; using $ARDUINO_OS_DATA" >&2
      export ARDUINO_DIRECTORIES_DATA="$ARDUINO_OS_DATA"
    fi
    unset view
  fi
  export ARDUINO_DIRECTORIES_DOWNLOADS="${ARDUINO_DIRECTORIES_DOWNLOADS:-${XDG_CACHE_HOME:-$HOME/.cache}/arduino/staging}"
  # The OS package manager updates arduino-cli: no update check over the network.
  export ARDUINO_UPDATER_ENABLE_NOTIFICATION="${ARDUINO_UPDATER_ENABLE_NOTIFICATION:-false}"
else
  [[ "${ARDUINO_DIRECTORIES_DATA:-}" != /opt/big-modular/* ]] || unset ARDUINO_DIRECTORIES_DATA
  [[ "${ARDUINO_DIRECTORIES_DOWNLOADS:-}" != "$HOME/.cache/arduino/staging" ]] || unset ARDUINO_DIRECTORIES_DOWNLOADS
  export PATH="$HOME/bin:$PATH"
  ARDUINO_CLI="${ARDUINO_CLI_BIN:-$(command -v arduino-cli 2>/dev/null || true)}"
fi

if [[ -z "$ARDUINO_CLI" || ! -x "$ARDUINO_CLI" ]]; then
  echo "arduino-cli not found. Run ./setup.sh first." >&2
  [[ "$ATTINY_TOOLCHAINS" != os ]] || \
    echo "(OS toolchains: install the azero firmware-toolchains packages, or BIG_MODULAR_TOOLCHAINS=home)" >&2
  exit 1
fi
echo "==> arduino-cli: $ARDUINO_CLI (data: ${ARDUINO_DIRECTORIES_DATA:-default}, $ATTINY_TOOLCHAINS toolchains)"
