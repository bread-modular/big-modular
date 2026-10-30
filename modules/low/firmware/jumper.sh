#!/usr/bin/env bash
#
# jumper.sh — sourced by compile.sh / flash.sh. Resolves the JP1 MIDI input
# setting from $1 (or $JP1, or an interactive prompt) and exports it with the
# mco sketch for the shared opt/attiny1616-tools scripts.
#
#   p   JP1 1-2 (protected NPN front end): RX inverted (PORT_INVEN on PB3)
#   d   JP1 2-3 (direct, as Bread Modular): no inversion

FW_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOLS_DIR="$FW_DIR/../../../opt/attiny1616-tools"
FIRMWARE=mco
SETTINGS=(p d)

JP1="${1:-${JP1:-}}"
if [[ -z "$JP1" ]]; then
  echo "==> Select the JP1 MIDI input setting on the board:"
  echo "  1) p  (JP1 1-2 = protected input)"
  echo "  2) d  (JP1 2-3 = direct input)"
  while true; do
    printf "Enter number (1-2): "
    read -r SEL
    if [[ "$SEL" =~ ^[1-2]$ ]]; then
      JP1="${SETTINGS[$((SEL - 1))]}"
      break
    fi
    echo "Invalid selection. Try again." >&2
  done
fi

case "$JP1" in
  p) MIDI_DEFINES="MIDI_RX_INVERT=1" ;;
  d) MIDI_DEFINES="MIDI_RX_INVERT=0" ;;
  *)
    echo "Unknown JP1 setting '$JP1' (expected: ${SETTINGS[*]})" >&2
    exit 1
    ;;
esac

echo "==> LOW $FIRMWARE firmware for JP1=$JP1 ($MIDI_DEFINES)"
export ATTINY_SKETCH_ROOT="$FW_DIR/$FIRMWARE"
export ATTINY_DEFINES="$MIDI_DEFINES"
