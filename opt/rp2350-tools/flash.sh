#!/usr/bin/env bash
# flash.sh — build an RP2350 Pico SDK project and load it over USB.
#
# Usage (through a module wrapper that sets RP2350_PROJECT_ROOT):
#   flash.sh                  # build, then load the UF2
#   flash.sh path/to/fw.uf2   # load an already-built UF2 (no build)
#   flash.sh info             # show the firmware on the board (picotool info -f)
#
# Before loading, the UF2's program information (name, version, description)
# is printed, so the console shows which firmware goes onto the board.
#
# No buttons are needed on a board that runs a Pico SDK USB stdio firmware:
#  1. `picotool load -f` (as Bread Modular) reboots it (USB reset interface)
#     into BOOTSEL, loads the UF2 and reboots into it.
#  2. If picotool can't (missing, or no USB permission: Linux without the udev
#     rule), the running board's USB serial port is opened at 1200 baud, which
#     makes the SDK firmware reboot into BOOTSEL; the RP2350 drive that shows
#     up (mounted with udisksctl on Linux if needed) gets the UF2 copied on.
# A board that does not answer (blank flash, crashed firmware): hold BOOT, tap
# RESET, release BOOT, then run this again. RP2350_SERIAL_PORT picks the port
# when several boards are attached.
#
# Linux: picotool needs USB access without sudo, see README.md (udev rule).
set -euo pipefail

TOOLS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$TOOLS_DIR/common.sh"

PICOTOOL_BIN="$(find_picotool || true)"

# Program name / version / description lines of `picotool info` (file or board).
program_info() {
  "$PICOTOOL_BIN" info "$@" 2>/dev/null | sed -n '/^Program Information/,/^$/{/^ \(name\|version\|description\):/p}'
}

if [[ "${1:-}" == "info" ]]; then
  [[ -n "$PICOTOOL_BIN" ]] || die "picotool not found (run ./setup.sh)"
  echo "==> Firmware on the board (picotool info -f):"
  INFO="$(program_info -f)" || true
  [[ -n "$INFO" ]] || die "no board answered (Linux: udev rule, see README.md; or hold BOOT, tap RESET)"
  echo "$INFO"
  exit 0
fi

resolve_project
if [[ -n "${1:-}" ]]; then
  UF2_PATH="$1"
  [[ "$UF2_PATH" == *.uf2 && -f "$UF2_PATH" ]] || die "not a UF2 file: $UF2_PATH"
else
  "$TOOLS_DIR/compile.sh"
fi

if [[ -n "$PICOTOOL_BIN" ]]; then
  echo "==> Firmware to flash ($UF2_PATH):"
  program_info "$UF2_PATH" || true
fi

find_volumes() {
  local base name v
  for base in /Volumes "/media/${USER:-$(id -un)}" "/run/media/${USER:-$(id -un)}"; do
    for name in RP2350 RPI-RP2; do
      for v in "$base/$name"*; do
        [[ -d "$v" && -f "$v/INFO_UF2.TXT" ]] && echo "$v"
      done
    done
  done
  return 0
}

# Linux: mount an unmounted BOOTSEL drive (udisks, no sudo on a desktop).
mount_bootsel_drive() {
  local dev
  command -v udisksctl >/dev/null 2>&1 || return 0
  for dev in /dev/disk/by-label/RP2350 /dev/disk/by-label/RPI-RP2; do
    [[ -e "$dev" ]] || continue
    findmnt -rn -S "$(readlink -f "$dev")" >/dev/null 2>&1 || udisksctl mount -b "$dev" >/dev/null 2>&1 || true
  done
}

# USB serial port(s) of a running RP2 firmware (vendor 2e8a).
find_serial_ports() {
  local tty dev
  if [[ -n "${RP2350_SERIAL_PORT:-}" ]]; then
    echo "$RP2350_SERIAL_PORT"
  elif [[ -d /sys/class/tty ]]; then
    for tty in /sys/class/tty/ttyACM*; do
      [[ -e "$tty/device" ]] || continue
      dev="$(readlink -f "$tty/device")"
      [[ "$(cat "$dev/../idVendor" 2>/dev/null)" == 2e8a ]] && echo "/dev/$(basename "$tty")"
    done
  else
    for dev in /dev/cu.usbmodem*; do
      [[ -e "$dev" ]] && echo "$dev"
    done
  fi
  return 0
}

# Open the port at 1200 baud: the Pico SDK USB stdio reboots into BOOTSEL.
touch_1200_baud() {
  if [[ "$(uname -s)" == Darwin ]]; then
    stty -f "$1" 1200 2>/dev/null || true
  else
    stty -F "$1" 1200 2>/dev/null || true
  fi
}

if [[ -n "$PICOTOOL_BIN" ]]; then
  echo "==> Loading $UF2_PATH with $PICOTOOL_BIN"
  if "$PICOTOOL_BIN" load -f "$UF2_PATH"; then
    echo "✅ Flash complete (the RP2350 rebooted into the new firmware)."
    exit 0
  fi
  echo "picotool could not load the board; trying a mounted BOOTSEL drive." >&2
else
  echo "picotool not found (run ./setup.sh); trying a mounted BOOTSEL drive." >&2
fi

[[ "$(uname -s)" == Darwin ]] || mount_bootsel_drive
mapfile -t VOLUMES < <(find_volumes)
if [[ ${#VOLUMES[@]} -eq 0 ]]; then
  mapfile -t PORTS < <(find_serial_ports)
  if [[ ${#PORTS[@]} -gt 1 ]]; then
    echo "Several RP2 serial ports found, set RP2350_SERIAL_PORT to one of:" >&2
    printf '  %s\n' "${PORTS[@]}" >&2
    exit 1
  elif [[ ${#PORTS[@]} -eq 1 ]]; then
    echo "==> Rebooting the board into BOOTSEL (1200 baud on ${PORTS[0]})"
    touch_1200_baud "${PORTS[0]}"
    for _ in $(seq 1 30); do
      sleep 0.5
      [[ "$(uname -s)" == Darwin ]] || mount_bootsel_drive
      mapfile -t VOLUMES < <(find_volumes)
      [[ ${#VOLUMES[@]} -eq 0 ]] || break
    done
  fi
fi
if [[ ${#VOLUMES[@]} -eq 0 ]]; then
  echo "No RP2350 BOOTSEL drive found. Hold BOOT, tap RESET, release BOOT, then retry" >&2
  echo "(Linux: mount the RP2350 drive, or add the picotool udev rule, see README.md)." >&2
  exit 1
elif [[ ${#VOLUMES[@]} -gt 1 ]]; then
  echo "Several BOOTSEL drives found, unplug all but one:" >&2
  printf '  %s\n' "${VOLUMES[@]}" >&2
  exit 1
fi
echo "==> Copying $UF2_PATH to ${VOLUMES[0]}"
cp "$UF2_PATH" "${VOLUMES[0]}/"
sync
echo "✅ Flash complete (the RP2350 reboots by itself)."
