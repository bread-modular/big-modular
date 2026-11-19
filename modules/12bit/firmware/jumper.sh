#!/usr/bin/env bash
#
# jumper.sh — sourced by compile.sh / flash.sh. Resolves the firmware from $1
# and the JP1 MIDI input setting from $2 (or $FIRMWARE / $JP1, or interactive
# prompts) and exports the project for the shared opt/stm32g0-tools scripts.
#
#   clapsnare | crash | osc3 | humtest
#   p   JP1 1-2 (protected NPN front end): RX inverted (USART1 RXINV on PB7)
#   d   JP1 2-3 (direct, as Bread Modular): no inversion
#   osc3 and humtest take no JP1 setting (a p|d argument is accepted and ignored).

FW_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOLS_DIR="$FW_DIR/../../../opt/stm32g0-tools"
FIRMWARES=(clapsnare crash osc3 humtest)
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
    if [[ "$SEL" =~ ^[1-4]$ ]]; then
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

export STM32_PROJECT_ROOT="$FW_DIR/$FIRMWARE"

if [[ "$FIRMWARE" == osc3 || "$FIRMWARE" == humtest ]]; then
  echo "==> 12bit $FIRMWARE firmware (JP1 not used)"
  export STM32_TARGET="$FIRMWARE"
  export STM32_BUILD_DIR="$FW_DIR/$FIRMWARE/.build"
  export STM32_DEFINES=""
  return 0
fi

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

echo "==> 12bit $FIRMWARE firmware for JP1=$JP1 ($MIDI_DEFINES)"
export STM32_TARGET="$FIRMWARE-$JP1"
export STM32_BUILD_DIR="$FW_DIR/$FIRMWARE/.build/$JP1"
export STM32_DEFINES="$MIDI_DEFINES"
