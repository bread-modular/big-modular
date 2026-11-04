#!/usr/bin/env bash
#
# compile.sh — build the DFU bootloader and the USB-AUDIO firmware:
#   usb-audio/.build/usb-audio.bin       application (0x4000), for the DFU bootloader
#   usb-audio/.build/usb-audio-full.bin  bootloader + application (0x0000), for the WCH ROM bootloader
# Arguments go to both makes instead (e.g. ./compile.sh clean).
#
set -euo pipefail

FW_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOLS="$FW_DIR/../../../opt/ch32v307-tools"
CH32_PROJECT_ROOT="$FW_DIR/bootloader" CH32_TARGET=bootloader "$TOOLS/compile.sh" "$@"
if [[ $# -gt 0 ]]; then
  CH32_PROJECT_ROOT="$FW_DIR/usb-audio" CH32_TARGET=usb-audio "$TOOLS/compile.sh" "$@"
else
  CH32_PROJECT_ROOT="$FW_DIR/usb-audio" CH32_TARGET=usb-audio "$TOOLS/compile.sh" all full
fi
