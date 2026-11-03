#!/usr/bin/env bash
#
# jumper.sh — sourced by compile.sh / flash.sh. Resolves the firmware from $1
# and the JP1 MIDI input setting from $2 (or $FIRMWARE / $JP1, or interactive
# prompts) and exports them for the shared opt/attiny1616-tools scripts.
#
#   noise   U2 (flash through J11, UPDI N)
#   hihat   U3 (flash through J12, UPDI H)
#   p   JP1 1-2 (protected NPN front end): RX inverted (PORT_INVEN on PB3)
#   d   JP1 2-3 (direct, as Bread Modular): no inversion
# Both MCUs share the RX net: build both for the same JP1 setting.
# JUMPER_ARGC = how many of the arguments were consumed (flash.sh passes the rest).

FW_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOLS_DIR="$FW_DIR/../../../opt/attiny1616-tools"
FIRMWARES=(noise hihat)
SETTINGS=(p d)

FIRMWARE="${1:-${FIRMWARE:-}}"
if [[ -z "$FIRMWARE" ]]; then
  echo "==> Select the firmware:"
  echo "  1) noise  (U2, UPDI N / J11)"
  echo "  2) hihat  (U3, UPDI H / J12)"
  while true; do
    printf "Enter number (1-2): "
    read -r SEL
    if [[ "$SEL" =~ ^[1-2]$ ]]; then
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

JUMPER_ARGC=2
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

echo "==> HATS $FIRMWARE firmware for JP1=$JP1 ($MIDI_DEFINES)"
export ATTINY_SKETCH_ROOT="$FW_DIR/$FIRMWARE"
export ATTINY_DEFINES="$MIDI_DEFINES"
