#!/usr/bin/env bash
# flash.sh — build and flash an ESP32-S3 ESP-IDF project over USB.
#
# Usage (through a module wrapper that sets ESP32_PROJECT_ROOT):
#   flash.sh                  # pick the serial port
#   flash.sh /dev/ttyACM0     # explicit port (macOS: /dev/cu.usbmodemXXXX)
#   MONITOR=1 flash.sh        # open idf.py monitor after flashing (Ctrl-] quits)
#
# The ESP32-S3 native USB (USB-Serial/JTAG) enumerates as /dev/ttyACM* on Linux
# and /dev/cu.usbmodem* on macOS. If it does not show up, hold BOOT, tap RESET,
# release BOOT and retry.
set -euo pipefail

TOOLS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$TOOLS_DIR/common.sh"

PORT="${1:-${PORT:-}}"
resolve_project

PORTS=()
add_port() {
  local p="$1" q
  [[ -n "$p" && -e "$p" ]] || return 0
  for q in "${PORTS[@]+"${PORTS[@]}"}"; do [[ "$q" == "$p" ]] && return 0; done
  PORTS+=("$p")
}
collect_ports() {
  local pattern p
  case "$(uname -s)" in
    Darwin) for pattern in /dev/cu.usbmodem* /dev/cu.usbserial* /dev/cu.wchusbserial* \
                           /dev/cu.SLAB_USBtoUART*; do
              for p in $pattern; do add_port "$p"; done
            done ;;
    Linux)  for pattern in /dev/ttyACM* /dev/ttyUSB*; do
              for p in $pattern; do add_port "$p"; done
            done ;;
  esac
}

if [[ -n "$PORT" && ! -e "$PORT" ]]; then
  echo "Serial port not found: $PORT" >&2
  collect_ports
  [[ ${#PORTS[@]} -gt 0 ]] && { echo "Candidate ports:" >&2; printf '  %s\n' "${PORTS[@]}" >&2; }
  exit 1
fi
if [[ -z "$PORT" ]]; then
  echo "==> Detecting serial ports ($(uname -s))..."
  collect_ports
  if [[ ${#PORTS[@]} -eq 0 ]]; then
    echo "No serial ports found. Plug in the module's USB-C (BOOT + RESET if needed)" >&2
    echo "and retry, or pass a port: ./flash.sh /dev/ttyACM0" >&2
    exit 1
  elif [[ ${#PORTS[@]} -eq 1 ]]; then
    PORT="${PORTS[0]}"
    echo "==> Only one serial port found: $PORT"
  else
    echo "==> Multiple serial ports found. Select the ESP32-S3:"
    for i in "${!PORTS[@]}"; do printf "  %d) %s\n" "$((i + 1))" "${PORTS[$i]}"; done
    while true; do
      printf "Enter number (1-%d): " "${#PORTS[@]}"
      read -r SEL
      if [[ "$SEL" =~ ^[0-9]+$ ]] && (( SEL >= 1 && SEL <= ${#PORTS[@]} )); then
        PORT="${PORTS[$((SEL - 1))]}"
        break
      fi
      echo "Invalid selection. Try again." >&2
    done
  fi
fi

activate_idf

echo "==> Building & flashing $PROJECT_DIR (port: $PORT${ESP32_DEFINES:+, $ESP32_DEFINES})"
cd "$PROJECT_DIR"
ACTIONS=(-p "$PORT" flash)
[[ "${MONITOR:-0}" == 1 ]] && ACTIONS+=(monitor)
idf.py "${IDF_DEFINE_ARGS[@]+"${IDF_DEFINE_ARGS[@]}"}" "${ACTIONS[@]}"

echo "✅ Flash complete."
