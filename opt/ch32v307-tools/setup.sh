#!/usr/bin/env bash
#
# setup.sh — one-time CH32V307 toolchain setup. Reuses what is already
# installed; downloads only the missing pinned pieces into $CH32_HOME
# (default ~/.big-modular/ch32v307):
#   xPack riscv-none-elf-gcc, TinyUSB (pinned commit), openwch/ch32v307 SDK
#   (pinned commit), wchisp (release binary).
#
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

mkdir -p "$CH32_HOME"

fetch() { # url dest
  echo "Downloading $1"
  curl -fL --retry 3 -o "$2" "$1"
}

if toolchain="$(find_toolchain)"; then
  echo "riscv-none-elf-gcc: $toolchain"
else
  tag="$(host_tag)" || die "no xPack toolchain for $(uname -sm); install riscv-none-elf-gcc and set CH32_TOOLCHAIN."
  name="xpack-riscv-none-elf-gcc-$XPACK_GCC_VERSION-$tag.tar.gz"
  url="https://github.com/xpack-dev-tools/riscv-none-elf-gcc-xpack/releases/download/v$XPACK_GCC_VERSION/$name"
  tmp="$(mktemp -d)"
  fetch "$url" "$tmp/$name"
  fetch "$url.sha" "$tmp/$name.sha"
  (cd "$tmp" && sha256sum -c "$name.sha" 2>/dev/null || shasum -a 256 -c "$name.sha")
  tar -xzf "$tmp/$name" -C "$CH32_HOME"
  rm -rf "$tmp"
  echo "riscv-none-elf-gcc: $(find_toolchain)"
fi

clone_pinned() { # url commit dest
  local tmp="$3.tmp"
  rm -rf "$tmp"
  git init -q "$tmp"
  git -C "$tmp" remote add origin "$1"
  git -C "$tmp" fetch -q --depth 1 origin "$2"
  git -C "$tmp" -c advice.detachedHead=false checkout -q FETCH_HEAD
  mv "$tmp" "$3"
}

if path="$(find_tinyusb)"; then
  echo "TinyUSB: $path"
else
  clone_pinned https://github.com/hathach/tinyusb.git "$TINYUSB_COMMIT" "$CH32_HOME/tinyusb-${TINYUSB_COMMIT:0:8}"
  echo "TinyUSB: $(find_tinyusb)"
fi

if path="$(find_wch_sdk)"; then
  echo "WCH SDK: $path"
else
  clone_pinned https://github.com/openwch/ch32v307.git "$WCH_SDK_COMMIT" "$CH32_HOME/ch32v307-${WCH_SDK_COMMIT:0:8}"
  echo "WCH SDK: $(find_wch_sdk)"
fi

if path="$(find_wchisp)"; then
  echo "wchisp: $path"
else
  case "$(host_tag)" in
    linux-x64) asset=linux-x64 ;;
    linux-arm64) asset=linux-aarch64 ;;
    darwin-arm64) asset=macos-arm64 ;;
    darwin-x64) asset=macos-x64 ;;
    *) die "no wchisp binary for $(uname -sm); cargo install wchisp" ;;
  esac
  dest="$CH32_HOME/wchisp-$WCHISP_VERSION"
  mkdir -p "$dest"
  fetch "https://github.com/ch32-rs/wchisp/releases/download/v$WCHISP_VERSION/wchisp-v$WCHISP_VERSION-$asset.tar.gz" \
        "$dest/wchisp.tar.gz"
  tar -xzf "$dest/wchisp.tar.gz" -C "$dest"
  rm "$dest/wchisp.tar.gz"
  [[ -x "$dest/wchisp" ]] || mv "$(find "$dest" -name wchisp -type f | head -1)" "$dest/wchisp"
  echo "wchisp: $(find_wchisp)"
fi

if [[ "$(uname -s)" == Linux ]] && ! grep -qs 4348 /etc/udev/rules.d/*.rules; then
  cat <<'EOF'

Note: no udev rule for the WCH bootloader (4348:55e0), so wchisp needs sudo.
One-time fix:
  echo 'SUBSYSTEM=="usb", ATTRS{idVendor}=="4348", ATTRS{idProduct}=="55e0", MODE="0660", TAG+="uaccess"' | \
    sudo tee /etc/udev/rules.d/99-wchisp.rules
  sudo udevadm control --reload-rules && sudo udevadm trigger
EOF
fi
