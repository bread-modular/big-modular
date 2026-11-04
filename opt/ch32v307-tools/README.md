# ch32v307-tools

Shared CH32V307 build / flash scripts for the modules' firmwares (TinyUSB +
the WCH peripheral library, bare metal, Make), the counterpart of
`opt/rp2350-tools` and `opt/esp32-tools`. Used by `modules/usb-audio/firmware/`.

| Script | Use |
|---|---|
| `setup.sh` | reuse installed tools; download only the missing pinned pieces into `$CH32_HOME` (default `~/.big-modular/ch32v307`) |
| `compile.sh` | `make` in `$CH32_PROJECT_ROOT` with the pinned toolchain / TinyUSB / SDK -> `<build>/<target>.{elf,bin,hex}` |
| `flash.sh [fw.bin]` | build (unless a binary is given), wait for the ROM USB bootloader (`4348:55e0`, `CH32_BOOT_WAIT` s, default 60), `wchisp flash` (writes, verifies, resets) |
| `common.sh` | sourced helpers |

Pinned dependencies (first hit wins; `compile.sh` / `flash.sh` never download):

| Tool | Version | Looked up in |
|---|---|---|
| xPack `riscv-none-elf-gcc` | 15.2.0-1 | `$CH32_TOOLCHAIN`, `$CH32_HOME/xpack-riscv-none-elf-gcc-<v>`, PATH |
| TinyUSB | master `8d265ad1` (2026-11-04; 0.21.0 lacks the WCH USBHS ISO / connect fixes) | `$TINYUSB_PATH`, `$CH32_HOME/tinyusb-8d265ad1` |
| openwch/ch32v307 EVT | `184f21b8` (the commit TinyUSB pins) | `$WCH_SDK_PATH`, `$CH32_HOME/ch32v307-184f21b8` |
| wchisp | 0.3.0 | `$WCHISP_BIN`, PATH, `~/.cargo/bin`, `$CH32_HOME/wchisp-<v>` |

Module wrappers set `CH32_PROJECT_ROOT` (dir with the Makefile),
`CH32_TARGET` (output name) and optionally `CH32_BUILD_DIR` (default
`<project>/.build`).

## Bootloader and Linux USB access

The CH32V307 ROM bootloader enumerates on the USBHS pins (PB6/PB7): hold
BOOT, press RESET, release BOOT. Without a udev rule `flash.sh` runs
`wchisp` through `sudo`. One-time:

```sh
echo 'SUBSYSTEM=="usb", ATTRS{idVendor}=="4348", ATTRS{idProduct}=="55e0", MODE="0660", TAG+="uaccess"' | \
  sudo tee /etc/udev/rules.d/99-wchisp.rules
sudo udevadm control --reload-rules && sudo udevadm trigger
```
