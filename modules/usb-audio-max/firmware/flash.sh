#!/usr/bin/env bash
#
# flash.sh — build the USB-AUDIO-MAX firmware and write it over the panel USB-C.
#
# Usage:
#   ./flash.sh          # application through the DFU bootloader: a running
#                       # firmware is switched to DFU over its console, no buttons
#   ./flash.sh --full   # bootloader + application through the WCH ROM bootloader:
#                       # first install / recovery. Hold BOOT (SW2), press RESET
#                       # (SW1), release BOOT; both buttons are on the carrier back.
#   ./flash.sh --bootloader  # only the DFU bootloader, through the running
#                       # firmware's console (blwrite), no buttons
#
# With the ROM bootloader already on USB, plain ./flash.sh writes the full image.
# USB IDs: firmware 1209:0003, DFU bootloader 1209:0004 (modules/usb-audio uses
# 0001 / 0002, so the two modules can share a host).
#
set -euo pipefail

FW_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOLS="$FW_DIR/../../../opt/ch32v307-tools"
BUILD="$FW_DIR/usb-audio-max/.build"

"$FW_DIR/compile.sh"

if [[ "${1:-}" == --bootloader ]]; then
  CH32_APP_ID=1209:0003 exec "$TOOLS/flash.sh" --blwrite "$FW_DIR/bootloader/.build/bootloader.bin"
fi
if [[ "${1:-}" == --full ]] || lsusb -d 4348:55e0 >/dev/null 2>&1; then
  exec "$TOOLS/flash.sh" "$BUILD/usb-audio-max-full.bin"
fi
CH32_DFU_ID=1209:0004 CH32_APP_ID=1209:0003 exec "$TOOLS/flash.sh" --dfu "$BUILD/usb-audio-max.bin"
