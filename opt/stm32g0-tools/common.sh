#!/usr/bin/env bash
# common.sh — shared helpers for the STM32G0 (bare-metal CMSIS) firmware
# scripts (sourced, not run).
#
# Module wrappers point the scripts at their firmware through the environment,
# as with opt/ch32v307-tools:
#   STM32_PROJECT_ROOT  dir with the firmware Makefile
#   STM32_TARGET        output name (default: project dir name)
#   STM32_BUILD_DIR     build dir (default: $STM32_PROJECT_ROOT/.build)
#   STM32_DEFINES       space-separated KEY=VALUE, passed to make as DEFINES
#
# Tools are looked up, never downloaded, here (setup.sh downloads). The CMSIS
# headers (and the home OpenOCD) are pinned and live in versioned dirs under
# $STM32_HOME.
#
# Where the tools come from (BIG_MODULAR_TOOLCHAINS):
#   os    the OS packages (azero): arm-none-eabi-gcc and openocd from /usr/bin,
#         CMSIS from /opt/big-modular/stm32g0, by explicit path (a home copy
#         earlier on the PATH is never picked). Default where
#         /opt/big-modular/stm32g0 exists.
#   home  the home installs as before: ~/.big-modular/stm32g0, the ARM GNU
#         14.2.rel1 of ~/.breadmodular (as opt/rp2350-tools), then the PATH.
#         Values under /opt/big-modular (from /etc/profile.d) are ignored.
#         Default where /opt/big-modular/stm32g0 does not exist.
# Explicit tool variables (ARM_TOOLCHAIN, CMSIS_*_PATH, OPENOCD_BIN) win in both.

STM32_OS_HOME=/opt/big-modular/stm32g0
case "${BIG_MODULAR_TOOLCHAINS:-}" in
  home) STM32_TOOLCHAINS=home ;;
  os) STM32_TOOLCHAINS=os ;;
  "") if [[ -d "$STM32_OS_HOME" ]]; then STM32_TOOLCHAINS=os; else STM32_TOOLCHAINS=home; fi ;;
  *) echo "Error: BIG_MODULAR_TOOLCHAINS must be 'os' or 'home', not '$BIG_MODULAR_TOOLCHAINS'" >&2; exit 1 ;;
esac
if [[ "$STM32_TOOLCHAINS" == os ]]; then
  STM32_HOME="${STM32_HOME:-$STM32_OS_HOME}"
else
  [[ "${STM32_HOME:-}" != /opt/big-modular/* ]] || unset STM32_HOME
  [[ "${BREADMODULAR_HOME:-}" != /opt/big-modular/* ]] || unset BREADMODULAR_HOME
  STM32_HOME="${STM32_HOME:-$HOME/.big-modular/stm32g0}"
fi
BREADMODULAR_HOME="${BREADMODULAR_HOME:-$HOME/.breadmodular}"

# ARM GNU toolchain of the home lookup (as opt/rp2350-tools; os: Arch's, any version)
TOOLCHAIN_VERSION="${TOOLCHAIN_VERSION:-14_2_Rel1}"
# STMicroelectronics/cmsis-device-g0 v1.4.5 (device header, startup, system)
CMSIS_G0_COMMIT="${CMSIS_G0_COMMIT:-f576c24e123edf3332988ecd49512c0f35f85186}"
# ARM-software/CMSIS_5 5.9.0 (CMSIS/Core/Include only)
CMSIS_CORE_COMMIT="${CMSIS_CORE_COMMIT:-2b7495b8535bdcb306dac29b9ded4cfb679d7e5c}"
# xPack OpenOCD (ST-Link or CMSIS-DAP SWD, target/stm32g0x.cfg)
XPACK_OPENOCD_VERSION="${XPACK_OPENOCD_VERSION:-0.12.0-7}"

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

# ARM GNU toolchain root (has bin/arm-none-eabi-gcc): $ARM_TOOLCHAIN -> os: /usr;
# home: ~/.breadmodular/toolchain/<v> -> ~/.pico-sdk/toolchain/<v> -> PATH.
find_toolchain() {
  local candidate gcc
  if [[ "$STM32_TOOLCHAINS" == os ]]; then
    for candidate in "${ARM_TOOLCHAIN:-}" /usr; do
      if [[ -n "$candidate" && -x "$candidate/bin/arm-none-eabi-gcc" ]]; then
        echo "$candidate"
        return 0
      fi
    done
    return 1
  fi
  for candidate in "${ARM_TOOLCHAIN:-}" "$BREADMODULAR_HOME/toolchain/$TOOLCHAIN_VERSION" \
                   "$HOME/.pico-sdk/toolchain/$TOOLCHAIN_VERSION"; do
    if [[ -n "$candidate" && -x "$candidate/bin/arm-none-eabi-gcc" ]]; then
      echo "$candidate"
      return 0
    fi
  done
  gcc="$(command -v arm-none-eabi-gcc 2>/dev/null)" || return 1
  dirname "$(dirname "$(readlink -f "$gcc")")"
}

find_cmsis_g0() {
  local candidate
  for candidate in "${CMSIS_G0_PATH:-}" "$STM32_HOME/cmsis-device-g0-${CMSIS_G0_COMMIT:0:8}"; do
    if [[ -n "$candidate" && -f "$candidate/Include/stm32g0xx.h" && \
          -f "$candidate/Source/Templates/gcc/startup_stm32g071xx.s" ]]; then
      echo "$candidate"
      return 0
    fi
  done
  return 1
}

find_cmsis_core() {
  local candidate
  for candidate in "${CMSIS_CORE_PATH:-}" "$STM32_HOME/cmsis-core-${CMSIS_CORE_COMMIT:0:8}"; do
    if [[ -n "$candidate" && -f "$candidate/CMSIS/Core/Include/core_cm0plus.h" ]]; then
      echo "$candidate"
      return 0
    fi
  done
  return 1
}

# OpenOCD with the STM32G0 target: $OPENOCD_BIN -> os: /usr/bin/openocd;
# home: $STM32_HOME xPack -> PATH.
find_openocd() {
  local candidate
  if [[ "$STM32_TOOLCHAINS" == os ]]; then
    for candidate in "${OPENOCD_BIN:-}" /usr/bin/openocd; do
      if [[ -n "$candidate" && -x "$candidate" ]]; then
        echo "$candidate"
        return 0
      fi
    done
    return 1
  fi
  for candidate in "${OPENOCD_BIN:-}" "$STM32_HOME/xpack-openocd-$XPACK_OPENOCD_VERSION/bin/openocd" \
                   "$(command -v openocd 2>/dev/null)"; do
    if [[ -n "$candidate" && -x "$candidate" ]]; then
      echo "$candidate"
      return 0
    fi
  done
  return 1
}

# Extra hint for a "not found" in os mode.
os_hint() {
  [[ "$STM32_TOOLCHAINS" == os ]] || return 0
  printf '%s' " (OS toolchains: install the azero firmware-toolchains packages, or BIG_MODULAR_TOOLCHAINS=home)"
}

# Resolve everything a build needs (no downloads).
activate_stm32() {
  ARM_TOOLCHAIN="$(find_toolchain)" || die "arm-none-eabi-gcc not found. Run ./setup.sh first.$(os_hint)"
  CMSIS_G0_PATH="$(find_cmsis_g0)" || die "cmsis-device-g0 ${CMSIS_G0_COMMIT:0:8} not found. Run ./setup.sh first.$(os_hint)"
  CMSIS_CORE_PATH="$(find_cmsis_core)" || die "CMSIS core ${CMSIS_CORE_COMMIT:0:8} not found. Run ./setup.sh first.$(os_hint)"
  [[ -n "${STM32_PROJECT_ROOT:-}" && -f "$STM32_PROJECT_ROOT/Makefile" ]] || \
    die "STM32_PROJECT_ROOT must point at a firmware dir with a Makefile."
  STM32_TARGET="${STM32_TARGET:-$(basename "$STM32_PROJECT_ROOT")}"
  STM32_BUILD_DIR="${STM32_BUILD_DIR:-$STM32_PROJECT_ROOT/.build}"
  export ARM_TOOLCHAIN CMSIS_G0_PATH CMSIS_CORE_PATH STM32_TARGET STM32_BUILD_DIR
}
