#!/usr/bin/env bash
# common.sh — shared helpers for the CH32V307 (TinyUSB + WCH SDK) firmware
# scripts (sourced, not run).
#
# Module wrappers point the scripts at their firmware through the environment,
# as with opt/rp2350-tools:
#   CH32_PROJECT_ROOT  dir with the firmware Makefile
#   CH32_TARGET        output name (default: project dir name)
#   CH32_BUILD_DIR     build dir (default: $CH32_PROJECT_ROOT/.build)
#
# Tools are looked up, never downloaded, here (setup.sh downloads). Every
# dependency is pinned and lives in its own versioned dir under $CH32_HOME.

CH32_HOME="${CH32_HOME:-$HOME/.big-modular/ch32v307}"

# xPack GNU RISC-V Embedded GCC (rv32imac, newlib-nano)
XPACK_GCC_VERSION="${XPACK_GCC_VERSION:-15.2.0-1}"
# TinyUSB master after the WCH USBHS ISO / connect fixes (0.21.0 lacks them)
TINYUSB_COMMIT="${TINYUSB_COMMIT:-8d265ad1f8cb82341acc59a7828eaf9e289063f7}"
# openwch/ch32v307 EVT (peripheral library, startup), the commit TinyUSB pins
WCH_SDK_COMMIT="${WCH_SDK_COMMIT:-184f21b852cb95eed58e86e901837bc9fff68775}"
WCHISP_VERSION="${WCHISP_VERSION:-0.3.0}"

die() {
  echo "Error: $*" >&2
  exit 1
}

host_tag() {
  case "$(uname -s)-$(uname -m)" in
    Linux-x86_64) echo linux-x64 ;;
    Linux-aarch64) echo linux-arm64 ;;
    Darwin-arm64) echo darwin-arm64 ;;
    Darwin-x86_64) echo darwin-x64 ;;
    *) return 1 ;;
  esac
}

# Toolchain root (has bin/riscv-none-elf-gcc): $CH32_TOOLCHAIN -> $CH32_HOME -> PATH.
find_toolchain() {
  local candidate gcc
  for candidate in "${CH32_TOOLCHAIN:-}" "$CH32_HOME/xpack-riscv-none-elf-gcc-$XPACK_GCC_VERSION"; do
    if [[ -n "$candidate" && -x "$candidate/bin/riscv-none-elf-gcc" ]]; then
      echo "$candidate"
      return 0
    fi
  done
  gcc="$(command -v riscv-none-elf-gcc 2>/dev/null)" || return 1
  dirname "$(dirname "$(readlink -f "$gcc")")"
}

find_tinyusb() {
  local candidate
  for candidate in "${TINYUSB_PATH:-}" "$CH32_HOME/tinyusb-${TINYUSB_COMMIT:0:8}"; do
    if [[ -n "$candidate" && -f "$candidate/src/tusb.h" && \
          -f "$candidate/src/portable/wch/dcd_ch32_usbhs.c" ]]; then
      echo "$candidate"
      return 0
    fi
  done
  return 1
}

find_wch_sdk() {
  local candidate
  for candidate in "${WCH_SDK_PATH:-}" "$CH32_HOME/ch32v307-${WCH_SDK_COMMIT:0:8}"; do
    if [[ -n "$candidate" && -f "$candidate/EVT/EXAM/SRC/Peripheral/inc/ch32v30x.h" ]]; then
      echo "$candidate"
      return 0
    fi
  done
  return 1
}

# wchisp (USB ISP flasher for the WCH ROM bootloader): $WCHISP_BIN -> PATH ->
# ~/.cargo/bin -> $CH32_HOME.
find_wchisp() {
  local candidate
  for candidate in "${WCHISP_BIN:-}" "$(command -v wchisp 2>/dev/null)" "$HOME/.cargo/bin/wchisp" \
                   "$CH32_HOME/wchisp-$WCHISP_VERSION/wchisp"; do
    if [[ -n "$candidate" && -x "$candidate" ]]; then
      echo "$candidate"
      return 0
    fi
  done
  return 1
}

# Resolve everything a build needs (no downloads).
activate_ch32() {
  CH32_TOOLCHAIN="$(find_toolchain)" || die "riscv-none-elf-gcc not found. Run ./setup.sh first."
  TINYUSB_PATH="$(find_tinyusb)" || die "TinyUSB ${TINYUSB_COMMIT:0:8} not found. Run ./setup.sh first."
  WCH_SDK_PATH="$(find_wch_sdk)" || die "WCH ch32v307 SDK ${WCH_SDK_COMMIT:0:8} not found. Run ./setup.sh first."
  [[ -n "${CH32_PROJECT_ROOT:-}" && -f "$CH32_PROJECT_ROOT/Makefile" ]] || \
    die "CH32_PROJECT_ROOT must point at a firmware dir with a Makefile."
  CH32_TARGET="${CH32_TARGET:-$(basename "$CH32_PROJECT_ROOT")}"
  CH32_BUILD_DIR="${CH32_BUILD_DIR:-$CH32_PROJECT_ROOT/.build}"
  export CH32_TOOLCHAIN TINYUSB_PATH WCH_SDK_PATH CH32_TARGET CH32_BUILD_DIR
}
