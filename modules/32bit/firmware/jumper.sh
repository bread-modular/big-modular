#!/usr/bin/env bash
#
# jumper.sh — sourced by compile.sh / flash.sh. Resolves the firmware
# (polysynth|fxrack) and the JP1 MIDI input setting, and exports them for
# opt/esp32-tools. The firmware name may come before or after the JP1 setting
# (`fxrack p` or `p fxrack`), or from $FIRMWARE. With ASK_FIRMWARE=1 (flash.sh)
# and no firmware given, it is picked from a menu (Enter = polysynth);
# otherwise it defaults to polysynth. JP1 comes from the arguments, $JP1 or a
# menu. JUMPER_ARGC = how many arguments were consumed (flash.sh passes the
# rest on as the port).
#
#   p   JP1 1-2 (protected NPN front end): RX inverted (UART_SIGNAL_RXD_INV)
#   d   JP1 2-3 (direct, as Bread Modular): no inversion

FW_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOLS_DIR="$FW_DIR/../../../opt/esp32-tools"
FIRMWARES=(polysynth fxrack)
SETTINGS=(p d)
DEFAULT_FIRMWARE=polysynth

is_firmware() { case " ${FIRMWARES[*]} " in *" ${1:-} "*) [[ -n "${1:-}" ]] ;; *) false ;; esac; }
is_setting() { case " ${SETTINGS[*]} " in *" ${1:-} "*) [[ -n "${1:-}" ]] ;; *) false ;; esac; }

JUMPER_ARGC=0
ARG_FIRMWARE=""
ARG_JP1=""
for arg in "${1:-}" "${2:-}"; do
  if [[ -z "$ARG_FIRMWARE" ]] && is_firmware "$arg"; then
    ARG_FIRMWARE="$arg"
  elif [[ -z "$ARG_JP1" ]] && is_setting "$arg"; then
    ARG_JP1="$arg"
  else
    break
  fi
  JUMPER_ARGC=$((JUMPER_ARGC + 1))
done
# An unknown first argument that is not a port is a typo, not a port.
if [[ $JUMPER_ARGC -eq 0 && -n "${1:-}" && "${1}" != /* ]]; then
  echo "Unknown argument '$1' (expected a firmware: ${FIRMWARES[*]}, a JP1 setting: ${SETTINGS[*]}, or a port)" >&2
  exit 1
fi

FIRMWARE="${ARG_FIRMWARE:-${FIRMWARE:-}}"
JP1="${ARG_JP1:-${JP1:-}}"

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

if [[ -z "$FIRMWARE" ]]; then
  if [[ "${ASK_FIRMWARE:-0}" == 1 ]]; then
    echo "==> Select the firmware to flash:"
    for i in "${!FIRMWARES[@]}"; do
      mark=""
      [[ "${FIRMWARES[$i]}" == "$DEFAULT_FIRMWARE" ]] && mark="  (default)"
      echo "  $((i + 1))) ${FIRMWARES[$i]}$mark"
    done
    while true; do
      printf "Enter number (1-%d, Enter = %s): " "${#FIRMWARES[@]}" "$DEFAULT_FIRMWARE"
      read -r SEL
      if [[ -z "$SEL" ]]; then
        FIRMWARE="$DEFAULT_FIRMWARE"
        break
      elif [[ "$SEL" =~ ^[0-9]+$ ]] && (( SEL >= 1 && SEL <= ${#FIRMWARES[@]} )); then
        FIRMWARE="${FIRMWARES[$((SEL - 1))]}"
        break
      fi
      echo "Invalid selection. Try again." >&2
    done
  else
    FIRMWARE="$DEFAULT_FIRMWARE"
  fi
fi
if ! is_firmware "$FIRMWARE"; then
  echo "Unknown firmware '$FIRMWARE' (expected: ${FIRMWARES[*]})" >&2
  exit 1
fi

echo "==> 32bit $FIRMWARE firmware for JP1=$JP1 ($MIDI_DEFINES)"
export ESP32_PROJECT_ROOT="$FW_DIR/$FIRMWARE"
export ESP32_DEFINES="$MIDI_DEFINES"
