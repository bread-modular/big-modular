#!/usr/bin/env bash
#
# setup.sh — one-time STM32G0 toolchain setup. Reuses what is already
# installed; downloads only the missing pinned pieces into $STM32_HOME
# (default ~/.big-modular/stm32g0):
#   cmsis-device-g0 (pinned commit), CMSIS_5 Core/Include (pinned commit,
#   sparse), xPack OpenOCD (release binary, sha256-checked).
# The ARM GNU toolchain is not downloaded: install Bread Modular's
# (~/.breadmodular, e.g. opt/rp2350-tools/setup.sh) or put arm-none-eabi-gcc
# on PATH.
#
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

mkdir -p "$STM32_HOME"

fetch() { # url dest
  echo "Downloading $1"
  curl -fL --retry 3 -o "$2" "$1"
}

if toolchain="$(find_toolchain)"; then
  echo "arm-none-eabi-gcc: $toolchain"
else
  die "arm-none-eabi-gcc not found: run opt/rp2350-tools/setup.sh (ARM GNU $TOOLCHAIN_VERSION) or set ARM_TOOLCHAIN."
fi

clone_pinned() { # url commit dest [sparse dir]
  local tmp="$3.tmp"
  rm -rf "$tmp"
  git init -q "$tmp"
  git -C "$tmp" remote add origin "$1"
  if [[ -n "${4:-}" ]]; then
    git -C "$tmp" sparse-checkout set --no-cone "/$4/"
    git -C "$tmp" fetch -q --depth 1 --filter=blob:none origin "$2"
  else
    git -C "$tmp" fetch -q --depth 1 origin "$2"
  fi
  git -C "$tmp" -c advice.detachedHead=false checkout -q FETCH_HEAD
  mv "$tmp" "$3"
}

if path="$(find_cmsis_g0)"; then
  echo "cmsis-device-g0: $path"
else
  clone_pinned https://github.com/STMicroelectronics/cmsis-device-g0.git "$CMSIS_G0_COMMIT" \
    "$STM32_HOME/cmsis-device-g0-${CMSIS_G0_COMMIT:0:8}"
  echo "cmsis-device-g0: $(find_cmsis_g0)"
fi

if path="$(find_cmsis_core)"; then
  echo "CMSIS core: $path"
else
  clone_pinned https://github.com/ARM-software/CMSIS_5.git "$CMSIS_CORE_COMMIT" \
    "$STM32_HOME/cmsis-core-${CMSIS_CORE_COMMIT:0:8}" CMSIS/Core/Include
  echo "CMSIS core: $(find_cmsis_core)"
fi

if path="$(find_openocd)"; then
  echo "openocd: $path"
else
  tag="$(host_tag)" || die "no xPack OpenOCD for $(uname -sm); install openocd and set OPENOCD_BIN."
  name="xpack-openocd-$XPACK_OPENOCD_VERSION-$tag.tar.gz"
  url="https://github.com/xpack-dev-tools/openocd-xpack/releases/download/v$XPACK_OPENOCD_VERSION/$name"
  tmp="$(mktemp -d)"
  fetch "$url" "$tmp/$name"
  fetch "$url.sha" "$tmp/$name.sha"
  (cd "$tmp" && { sha256sum -c "$name.sha" 2>/dev/null || shasum -a 256 -c "$name.sha"; })
  tar -xzf "$tmp/$name" -C "$STM32_HOME"
  rm -rf "$tmp"
  echo "openocd: $(find_openocd)"
fi

if [[ "$(uname -s)" == Linux ]] && ! grep -qs 0483 /etc/udev/rules.d/*.rules /lib/udev/rules.d/*.rules; then
  cat <<'NOTE'

Note: no udev rule for ST-Link probes (0483:*), so openocd may need sudo.
One-time fix:
  echo 'SUBSYSTEM=="usb", ATTRS{idVendor}=="0483", MODE="0660", TAG+="uaccess"' | \
    sudo tee /etc/udev/rules.d/99-stlink.rules
  sudo udevadm control --reload-rules && sudo udevadm trigger
NOTE
fi
