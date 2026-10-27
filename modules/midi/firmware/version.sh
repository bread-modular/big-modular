#!/usr/bin/env bash
#
# version.sh — sourced by compile.sh / flash.sh. Resolves the hardware version
# from $1 (or $MIDI_VERSION, or an interactive prompt) and exports the defines
# for the shared opt/attiny1616-tools scripts.
#
#   v1         hardware/v1: direct input, no RX inversion
#   v2         hardware/v2, JP2 1-2 (protected NPN input): RX inverted (PORT_INVEN)
#   v2-direct  hardware/v2, JP2 2-3 (debug bypass, V1 direct path): no inversion

FW_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOLS_DIR="$FW_DIR/../../../opt/attiny1616-tools"
VERSIONS=(v1 v2 v2-direct)

MIDI_VERSION="${1:-${MIDI_VERSION:-}}"
if [[ -z "$MIDI_VERSION" ]]; then
  echo "==> Select the MIDI hardware version:"
  echo "  1) v1         (V1.0 board)"
  echo "  2) v2         (V2.0 board, JP2 1-2 = protected input)"
  echo "  3) v2-direct  (V2.0 board, JP2 2-3 = debug bypass)"
  while true; do
    printf "Enter number (1-3): "
    read -r SEL
    if [[ "$SEL" =~ ^[1-3]$ ]]; then
      MIDI_VERSION="${VERSIONS[$((SEL - 1))]}"
      break
    fi
    echo "Invalid selection. Try again." >&2
  done
fi

case "$MIDI_VERSION" in
  v1)        MIDI_DEFINES="MIDI_HW_VERSION=1 MIDI_RX_INVERT=0" ;;
  v2)        MIDI_DEFINES="MIDI_HW_VERSION=2 MIDI_RX_INVERT=1" ;;
  v2-direct) MIDI_DEFINES="MIDI_HW_VERSION=2 MIDI_RX_INVERT=0" ;;
  *)
    echo "Unknown version '$MIDI_VERSION' (expected: ${VERSIONS[*]})" >&2
    exit 1
    ;;
esac

echo "==> MIDI firmware for $MIDI_VERSION ($MIDI_DEFINES)"
export ATTINY_SKETCH_ROOT="$FW_DIR"
export ATTINY_DEFINES="$MIDI_DEFINES"
