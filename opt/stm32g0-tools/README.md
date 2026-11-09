# stm32g0-tools

Shared STM32G0 build / flash scripts for the modules' firmwares (bare metal,
CMSIS headers only, Make), the counterpart of `opt/ch32v307-tools` and
`opt/rp2350-tools`. Used by `modules/hats/firmware/` (STM32G071C8T6); the
modules/12bit MCU is the same part.

| Script | Use |
|---|---|
| `setup.sh` | reuse installed tools; download only the missing pinned pieces into `$STM32_HOME` (default `~/.big-modular/stm32g0`) |
| `compile.sh` | `make` in `$STM32_PROJECT_ROOT` with the pinned toolchain / CMSIS -> `<build>/<target>.{elf,bin,hex}` |
| `flash.sh [fw.elf]` | build (unless an image is given), then OpenOCD over SWD with an ST-Link: program, verify, reset |
| `common.sh` | sourced helpers |

Pinned dependencies (first hit wins; `compile.sh` / `flash.sh` never download):

| Tool | Version | Looked up in |
|---|---|---|
| ARM GNU `arm-none-eabi-gcc` | 14.2.rel1 (`14_2_Rel1`, Bread Modular's, as `opt/rp2350-tools`; not downloaded) | `$ARM_TOOLCHAIN`, `~/.breadmodular/toolchain/14_2_Rel1`, `~/.pico-sdk/toolchain/14_2_Rel1`, PATH |
| STMicroelectronics `cmsis-device-g0` | v1.4.5 `f576c24e` (device header, startup, `system_stm32g0xx.c`; Apache-2.0) | `$CMSIS_G0_PATH`, `$STM32_HOME/cmsis-device-g0-f576c24e` |
| ARM `CMSIS_5` Core/Include | 5.9.0 `2b7495b8` (sparse checkout; Apache-2.0) | `$CMSIS_CORE_PATH`, `$STM32_HOME/cmsis-core-2b7495b8` |
| xPack OpenOCD | 0.12.0-7 (sha256-checked; `target/stm32g0x.cfg`) | `$OPENOCD_BIN`, `$STM32_HOME/xpack-openocd-0.12.0-7`, PATH |

Module wrappers set `STM32_PROJECT_ROOT` (dir with the Makefile),
`STM32_TARGET` (output name), optionally `STM32_BUILD_DIR` (default
`<project>/.build`) and `STM32_DEFINES` (`KEY=VALUE ...`, passed to make as
`DEFINES`). The Makefile gets `CROSS_COMPILE`, `CMSIS_G0_PATH`,
`CMSIS_CORE_PATH`, `BUILD`, `TARGET` and `DEFINES`; the linker script lives
with the firmware (see `modules/hats/firmware/hats/`).

## Probe and Linux USB access

`flash.sh` uses `interface/stlink.cfg` (any ST-Link V2/V3; `OPENOCD_INTERFACE`
picks another probe config). Wire it to the module's 1x5 SWD header (+3V3 as
VTref, SWDIO, SWCLK, GND, NRST) and power the module from its Eurorack header.
Without a udev rule `flash.sh` runs OpenOCD through `sudo`. One-time:

```sh
echo 'SUBSYSTEM=="usb", ATTRS{idVendor}=="0483", MODE="0660", TAG+="uaccess"' | \
  sudo tee /etc/udev/rules.d/99-stlink.rules
sudo udevadm control --reload-rules && sudo udevadm trigger
```
