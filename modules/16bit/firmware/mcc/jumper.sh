#!/usr/bin/env bash
#
# jumper.sh — sourced by compile.sh / flash.sh. Resolves the JP1 MIDI input
# setting from $1 (or $JP1, or a prompt) and the MCC unit from $2 (or $UNIT,
# or a prompt), and exports them with the cpx4_mcc sketch for the shared
# opt/attiny1616-tools scripts.
#
#   JP1  p   JP1 1-2 (protected NPN front end): RX inverted (PORT_INVEN on PB3)
#        d   JP1 2-3 (direct, as Bread Modular): no inversion
#   UNIT 1   MCC-1 "VOICE": CC20-23 + button CC102 (FM routing)
#        2   MCC-2 "FX":    CC27-30 + button CC103 (RESONANCE)

FW_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOLS_DIR="$FW_DIR/../../../../opt/attiny1616-tools"
FIRMWARE=cpx4_mcc
SETTINGS=(p d)
UNITS=(1 2)

JP1="${1:-${JP1:-}}"
if [[ -z "$JP1" ]]; then
  echo "==> Select the JP1 MIDI input setting on the MCC board:"
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

UNIT="${2:-${UNIT:-}}"
if [[ -z "$UNIT" ]]; then
  echo "==> Select the MCC unit:"
  echo "  1) MCC-1 VOICE (SHARP A, SHARP B, MOD, DRIVE; button = FM routing)"
  echo "  2) MCC-2 FX    (DELAY TIME, FEEDBACK, DELAY MIX, CUTOFF; button = RESONANCE)"
  while true; do
    printf "Enter number (1-2): "
    read -r UNIT
    [[ "$UNIT" =~ ^[1-2]$ ]] && break
    echo "Invalid selection. Try again." >&2
  done
fi

case "$UNIT" in
  1|2) ;;
  *)
    echo "Unknown MCC unit '$UNIT' (expected: ${UNITS[*]})" >&2
    exit 1
    ;;
esac

echo "==> cpx4 MCC-$UNIT firmware for JP1=$JP1 ($MIDI_DEFINES MCC_UNIT=$UNIT)"
export ATTINY_SKETCH_ROOT="$FW_DIR/$FIRMWARE"
export ATTINY_DEFINES="$MIDI_DEFINES MCC_UNIT=$UNIT"
