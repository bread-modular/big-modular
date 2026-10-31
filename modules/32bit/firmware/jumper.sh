#!/usr/bin/env bash
#
# jumper.sh — sourced by compile.sh / flash.sh. Resolves the JP1 MIDI input
# setting from $1 (or $JP1, or an interactive prompt) and the firmware from
# $FIRMWARE (default polysynth), and exports them for opt/esp32-tools.
#
#   p   JP1 1-2 (protected NPN front end): RX inverted (UART_SIGNAL_RXD_INV)
#   d   JP1 2-3 (direct, as Bread Modular): no inversion

FW_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOLS_DIR="$FW_DIR/../../../opt/esp32-tools"
FIRMWARES=(polysynth)
SETTINGS=(p d)

FIRMWARE="${FIRMWARE:-polysynth}"
case " ${FIRMWARES[*]} " in
  *" $FIRMWARE "*) ;;
  *)
    echo "Unknown firmware '$FIRMWARE' (expected: ${FIRMWARES[*]})" >&2
    exit 1
    ;;
esac

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

echo "==> 32bit $FIRMWARE firmware for JP1=$JP1 ($MIDI_DEFINES)"
export ESP32_PROJECT_ROOT="$FW_DIR/$FIRMWARE"
export ESP32_DEFINES="$MIDI_DEFINES"
