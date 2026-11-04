#!/usr/bin/env bash
#
# flash.sh — build the USB-AUDIO firmware and write it over the panel USB-C.
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
#
set -euo pipefail

FW_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOLS="$FW_DIR/../../../opt/ch32v307-tools"
BUILD="$FW_DIR/usb-audio/.build"

"$FW_DIR/compile.sh"

if [[ "${1:-}" == --bootloader ]]; then
  CH32_APP_ID=1209:0001 exec "$TOOLS/flash.sh" --blwrite "$FW_DIR/bootloader/.build/bootloader.bin"
fi
if [[ "${1:-}" == --full ]] || lsusb -d 4348:55e0 >/dev/null 2>&1; then
  exec "$TOOLS/flash.sh" "$BUILD/usb-audio-full.bin"
fi
CH32_DFU_ID=1209:0002 CH32_APP_ID=1209:0001 exec "$TOOLS/flash.sh" --dfu "$BUILD/usb-audio.bin"
