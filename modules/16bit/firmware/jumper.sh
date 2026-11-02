#!/usr/bin/env bash
#
# jumper.sh — sourced by compile.sh / flash.sh / package.sh. Resolves the JP1
# MIDI input setting from $1 (or $JP1, or an interactive prompt) and the app
# from $2 (or $APP, or APP_NAME in 16bit/.config, default polysynth), and
# exports them for opt/rp2350-tools. With ASK_APP=1 (flash.sh) and no app on
# the command line or in $APP, the app is picked from a menu (Enter keeps the
# .config / polysynth default).
#
#   p   JP1 1-2 (protected NPN front end): GPIO5 RX inverted (gpio_set_inover)
#   d   JP1 2-3 (direct, as Bread Modular): no inversion

FW_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOLS_DIR="$FW_DIR/../../../opt/rp2350-tools"
PROJECT="$FW_DIR/16bit"
# Keep in sync with VALID_APPS in 16bit/CMakeLists.txt
APPS=(noop sampler polysynth fxrack elab monosynth)
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

APP_NAME="${2:-${APP:-}}"
if [[ -z "$APP_NAME" ]]; then
  DEFAULT_APP=""
  if [[ -f "$PROJECT/.config" ]]; then
    DEFAULT_APP="$(sed -n 's/^[[:space:]]*APP_NAME[[:space:]]*=[[:space:]]*\([^[:space:]#]*\).*/\1/p' \
      "$PROJECT/.config" | tail -n 1)"
  fi
  DEFAULT_APP="${DEFAULT_APP:-polysynth}"
  if [[ "${ASK_APP:-0}" == 1 ]]; then
    echo "==> Select the firmware (app) to flash:"
    for i in "${!APPS[@]}"; do
      mark=""
      [[ "${APPS[$i]}" == "$DEFAULT_APP" ]] && mark="  (default)"
      echo "  $((i + 1))) ${APPS[$i]}$mark"
    done
    while true; do
      printf "Enter number (1-%d, Enter = %s): " "${#APPS[@]}" "$DEFAULT_APP"
      read -r SEL
      if [[ -z "$SEL" ]]; then
        APP_NAME="$DEFAULT_APP"
        break
      elif [[ "$SEL" =~ ^[0-9]+$ ]] && (( SEL >= 1 && SEL <= ${#APPS[@]} )); then
        APP_NAME="${APPS[$((SEL - 1))]}"
        break
      fi
      echo "Invalid selection. Try again." >&2
    done
  else
    APP_NAME="$DEFAULT_APP"
  fi
fi
case " ${APPS[*]} " in
  *" $APP_NAME "*) ;;
  *)
    echo "Unknown app '$APP_NAME' (expected: ${APPS[*]})" >&2
    exit 1
    ;;
esac

echo "==> 16bit $APP_NAME firmware for JP1=$JP1 ($MIDI_DEFINES)"
export RP2350_PROJECT_ROOT="$PROJECT"
export RP2350_TARGET=16bit
export RP2350_DEFINES="APP_NAME=$APP_NAME $MIDI_DEFINES"
