#!/usr/bin/env bash
#
# flash.sh [fw.elf] — build (unless an image is given) and write it over SWD
# with an ST-Link and OpenOCD (target/stm32g0x.cfg): program, verify, reset.
#
# Wire the probe to the module's 1x5 SWD header (+3V3 = VTref sense, SWDIO,
# SWCLK, GND, NRST) and power the module from its Eurorack header.
# OPENOCD_INTERFACE overrides the probe config (default interface/stlink.cfg).
#
set -euo pipefail

TOOLS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$TOOLS_DIR/common.sh"

if [[ -n "${1:-}" ]]; then
  IMAGE="$1"
  [[ -f "$IMAGE" ]] || die "$IMAGE not found"
else
  "$TOOLS_DIR/compile.sh"
  activate_stm32
  IMAGE="$STM32_BUILD_DIR/$STM32_TARGET.elf"
fi

OPENOCD="$(find_openocd)" || die "openocd not found. Run ./setup.sh first."

SUDO=()
if [[ "$(uname -s)" == Linux ]] && ! grep -qs 0483 /etc/udev/rules.d/*.rules /lib/udev/rules.d/*.rules; then
  SUDO=(sudo)   # no udev rule for the ST-Link (see setup.sh)
fi

"${SUDO[@]}" "$OPENOCD" -f "${OPENOCD_INTERFACE:-interface/stlink.cfg}" -f target/stm32g0x.cfg \
  -c "program {$IMAGE} verify reset exit"
