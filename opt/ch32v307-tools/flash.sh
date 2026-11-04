#!/usr/bin/env bash
#
# flash.sh [fw.bin]        — build (unless a binary is given) and write it from
#                            0x0000 through the CH32V307 ROM USB bootloader
#                            (4348:55e0) with wchisp, then reset.
# flash.sh --dfu [app.bin] — build (unless a binary is given) and write the
#                            application through the module's DFU bootloader
#                            ($CH32_DFU_ID, vid:pid) with dfu-util. A running
#                            firmware ($CH32_APP_ID) is first switched to DFU with a
#                            1200 baud touch on its CDC console (Linux), so no
#                            buttons are needed.
# flash.sh --blwrite boot.bin — rewrite the module's own bootloader through the
#                            running firmware's console (`blwrite`, see
#                            console_blwrite.py), then reboot it and wait for it.
#
# Enter the ROM bootloader: hold BOOT, press RESET, release BOOT.
#
set -euo pipefail

TOOLS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$TOOLS_DIR/common.sh"

MODE=rom
if [[ "${1:-}" == --dfu ]]; then
  MODE=dfu
  shift
elif [[ "${1:-}" == --blwrite ]]; then
  MODE=blwrite
  shift
  [[ -f "${1:-}" ]] || die "--blwrite needs the bootloader image"
fi

if [[ -n "${1:-}" ]]; then
  BIN="$1"
  [[ -f "$BIN" ]] || die "$BIN not found"
else
  "$TOOLS_DIR/compile.sh"
  activate_ch32
  BIN="$CH32_BUILD_DIR/$CH32_TARGET.bin"
fi

on_usb() { # vid:pid
  lsusb -d "$1" >/dev/null 2>&1
}

wait_usb() { # vid:pid seconds
  local i
  for i in $(seq 1 "$2"); do
    on_usb "$1" && return 0
    sleep 1
  done
  return 1
}

# sudo unless a udev rule grants access to vid:pid.
sudo_for() {
  local vid="${1%%:*}" pid="${1##*:}"
  if [[ "$(uname -s)" == Linux ]] && \
     ! grep -qsiE "idVendor[^,]*\"$vid\".*idProduct[^,]*\"$pid\"" /etc/udev/rules.d/*.rules; then
    echo sudo
  fi
}

# /dev/ttyACMn of the CDC console of the USB device vid:pid (Linux sysfs).
console_tty() {
  local vid="${1%%:*}" pid="${1##*:}" tty dev
  for tty in /sys/class/tty/ttyACM*; do
    [[ -e "$tty/device" ]] || continue
    dev="$(readlink -f "$tty/device/..")"
    if [[ "$(cat "$dev/idVendor" 2>/dev/null)" == "$vid" && \
          "$(cat "$dev/idProduct" 2>/dev/null)" == "$pid" ]]; then
      echo "/dev/$(basename "$tty")"
      return 0
    fi
  done
  return 1
}

if [[ "$MODE" == rom ]]; then
  WCHISP="$(find_wchisp)" || die "wchisp not found. Run ./setup.sh first."
  SUDO=()
  if [[ "$(uname -s)" == Linux ]] && ! grep -qs 4348 /etc/udev/rules.d/*.rules; then
    SUDO=(sudo)   # no udev rule for the bootloader (see setup.sh)
  fi

  if ! on_usb 4348:55e0; then
    wait_s="${CH32_BOOT_WAIT:-60}"
    echo "No CH32V307 bootloader on USB. Hold BOOT, press RESET, release BOOT (waiting $wait_s s)..."
    wait_usb 4348:55e0 "$wait_s" || die "bootloader (4348:55e0) did not appear"
    sleep 1   # let it finish enumerating
  fi

  "${SUDO[@]}" "$WCHISP" info
  "${SUDO[@]}" "$WCHISP" flash "$BIN"
  exit 0
fi

if [[ "$MODE" == blwrite ]]; then
  [[ -n "${CH32_APP_ID:-}" ]] || die "CH32_APP_ID (vid:pid of the firmware) not set"
  tty="$(console_tty "$CH32_APP_ID")" || die "the firmware ($CH32_APP_ID) is not on USB"
  echo "Writing $(basename "$BIN") through $tty..."
  python3 -I "$TOOLS_DIR/console_blwrite.py" "$tty" "$BIN"
  echo "Rebooted through the new bootloader; waiting for the firmware..."
  sleep 2
  wait_usb "$CH32_APP_ID" 20 || die "the firmware did not come back on USB (recovery: ./flash.sh --full)"
  echo "Firmware running."
  exit 0
fi

[[ -n "${CH32_DFU_ID:-}" ]] || die "CH32_DFU_ID (vid:pid of the DFU bootloader) not set"
command -v dfu-util >/dev/null || die "dfu-util not found (Debian/Ubuntu: sudo apt install dfu-util)"

if ! on_usb "$CH32_DFU_ID"; then
  if [[ -n "${CH32_APP_ID:-}" ]] && on_usb "$CH32_APP_ID"; then
    tty="$(console_tty "$CH32_APP_ID")" || die "$CH32_APP_ID has no console tty: type 'dfu' in its console"
    echo "Switching $CH32_APP_ID ($tty) to its DFU bootloader..."
    stty -F "$tty" 1200 hupcl
  else
    echo "Neither the firmware nor its DFU bootloader is on USB; waiting..."
  fi
  wait_usb "$CH32_DFU_ID" "${CH32_BOOT_WAIT:-15}" || \
    die "DFU bootloader ($CH32_DFU_ID) did not appear (first install / recovery: ./flash.sh --full)"
  sleep 1
fi

$(sudo_for "$CH32_DFU_ID") dfu-util -d "$CH32_DFU_ID" -a 0 -D "$BIN"

if [[ -n "${CH32_APP_ID:-}" ]]; then
  echo "Waiting for the new firmware ($CH32_APP_ID)..."
  wait_usb "$CH32_APP_ID" 20 || die "the firmware did not come back on USB"
  echo "Firmware running."
fi
