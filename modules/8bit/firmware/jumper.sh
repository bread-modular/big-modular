#!/usr/bin/env bash
#
# jumper.sh — sourced by compile.sh / flash.sh. Resolves the firmware from $1
# and the JP1 MIDI input setting from $2 (or $FIRMWARE / $JP1, or interactive
# prompts) and exports them for the shared opt/attiny1616-tools scripts.
#
#   drums | supersaw | crash
#   p   JP1 1-2 (protected NPN front end): RX inverted (PORT_INVEN on PB3)
#   d   JP1 2-3 (direct, as Bread Modular): no inversion

FW_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOLS_DIR="$FW_DIR/../../../opt/attiny1616-tools"
FIRMWARES=(drums supersaw crash)
SETTINGS=(p d)

FIRMWARE="${1:-${FIRMWARE:-}}"
if [[ -z "$FIRMWARE" ]]; then
  echo "==> Select the firmware:"
  for i in "${!FIRMWARES[@]}"; do
    printf "  %d) %s\n" "$((i + 1))" "${FIRMWARES[$i]}"
  done
  while true; do
    printf "Enter number (1-%d): " "${#FIRMWARES[@]}"
    read -r SEL
    if [[ "$SEL" =~ ^[1-3]$ ]]; then
      FIRMWARE="${FIRMWARES[$((SEL - 1))]}"
      break
    fi
    echo "Invalid selection. Try again." >&2
  done
fi
case " ${FIRMWARES[*]} " in
  *" $FIRMWARE "*) ;;
  *)
    echo "Unknown firmware '$FIRMWARE' (expected: ${FIRMWARES[*]})" >&2
    exit 1
    ;;
esac

JP1="${2:-${JP1:-}}"
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

echo "==> 8bit $FIRMWARE firmware for JP1=$JP1 ($MIDI_DEFINES)"
export ATTINY_SKETCH_ROOT="$FW_DIR/$FIRMWARE"
export ATTINY_DEFINES="$MIDI_DEFINES"
