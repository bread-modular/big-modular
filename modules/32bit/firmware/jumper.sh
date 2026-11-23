#!/usr/bin/env bash
#
# jumper.sh — sourced by compile.sh / flash.sh. Resolves the firmware
# (polysynth|fxrack|master) and the JP1 MIDI input setting, and exports them for
# opt/esp32-tools. The firmware name may come before or after the JP1 setting
# (`fxrack p` or `p fxrack`), or from $FIRMWARE. With ASK_FIRMWARE=1 (flash.sh)
# and no firmware given, it is picked from a menu (Enter = polysynth);
# otherwise it defaults to polysynth. JP1 comes from the arguments, $JP1 or a
# menu. JUMPER_ARGC = how many arguments were consumed (flash.sh passes the
# rest on as the port).
#
#   p   JP1 1-2 (protected NPN front end): RX inverted (UART_SIGNAL_RXD_INV)
#   d   JP1 2-3 (direct, as Bread Modular): no inversion
#
# BOARD=es1 builds for the 32bit ES1 board (codec clock master); default BOARD=s3.
#
# master has no MIDI: it needs no JP1 setting (`./compile.sh master`), and one
# given anyway is ignored.

FW_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOLS_DIR="$FW_DIR/../../../opt/esp32-tools"
FIRMWARES=(polysynth fxrack master)
NO_MIDI_FIRMWARES=(master)
SETTINGS=(p d)
DEFAULT_FIRMWARE=polysynth

uses_midi() { case " ${NO_MIDI_FIRMWARES[*]} " in *" ${1:-} "*) false ;; *) true ;; esac; }
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

if ! uses_midi "$FIRMWARE"; then
  JP1=""
elif [[ -z "$JP1" ]]; then
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
  "") MIDI_DEFINES="" ;;
  p) MIDI_DEFINES="MIDI_RX_INVERT=1" ;;
  d) MIDI_DEFINES="MIDI_RX_INVERT=0" ;;
  *)
    echo "Unknown JP1 setting '$JP1' (expected: ${SETTINGS[*]})" >&2
    exit 1
    ;;
esac

if [[ -n "$JP1" ]]; then
  echo "==> 32bit $FIRMWARE firmware for JP1=$JP1 ($MIDI_DEFINES)"
else
  echo "==> 32bit $FIRMWARE firmware (no MIDI, no JP1 setting)"
fi
# Board: BOARD=s3 (default; the S3 board, ESP32-S3 makes the codec MCLK) or BOARD=es1 (the ES1 board:
# Y2 clocks the ES8388, which is the I2S master; docs/research.md section 10).
case "${BOARD:-s3}" in
  s3) CODEC_DEFINES="CODEC_CLOCK_MASTER=0" ;;
  es1) CODEC_DEFINES="CODEC_CLOCK_MASTER=1" ;;
  *)
    echo "Unknown BOARD '${BOARD}' (expected: s3, es1)" >&2
    exit 1
    ;;
esac
echo "==> Board ${BOARD:-s3} ($CODEC_DEFINES)"
export ESP32_PROJECT_ROOT="$FW_DIR/$FIRMWARE"
export ESP32_DEFINES="${MIDI_DEFINES:+$MIDI_DEFINES }$CODEC_DEFINES"
