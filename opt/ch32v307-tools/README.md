# ch32v307-tools

Shared CH32V307 build / flash scripts for the modules' firmwares (TinyUSB +
the WCH peripheral library, bare metal, Make), the counterpart of
`opt/rp2350-tools` and `opt/esp32-tools`. Used by `modules/usb-audio/firmware/`.

| Script | Use |
|---|---|
| `setup.sh` | reuse installed tools; download only the missing pinned pieces into `$CH32_HOME` (default `~/.big-modular/ch32v307`; OS packages: check only) |
| `compile.sh` | `make` in `$CH32_PROJECT_ROOT` with the pinned toolchain / TinyUSB / SDK -> `<build>/<target>.{elf,bin,hex}` |
| `flash.sh [fw.bin]` | build (unless a binary is given), wait for the ROM USB bootloader (`4348:55e0`, `CH32_BOOT_WAIT` s, default 60), `wchisp flash` (writes, verifies, resets) |
| `common.sh` | sourced helpers |

## OS toolchains (azero) and the home fallback

Where `/opt/big-modular/ch32v307` exists (azero's OS packages) the scripts default
to `BIG_MODULAR_TOOLCHAINS=os`: `$CH32_HOME` = `/opt/big-modular/ch32v307` with the same xPack GCC 15.2.0-1 (byte-identical binaries), TinyUSB, WCH SDK and wchisp 0.3.0, and `/usr/bin/dfu-util`. They are resolved by explicit path, so
a home copy earlier on the PATH (`~/.local/bin`, `~/bin`, `~/.cargo/bin`) is
never picked, in any shell, login or not (the `/etc/profile.d/big-modular-*.sh`
variables are not needed). `setup.sh` then only checks: nothing is downloaded
or written. `BIG_MODULAR_TOOLCHAINS=home` restores the home lookup below
(`/opt/big-modular` values exported by `/etc/profile.d` are ignored). Without
`/opt/big-modular/ch32v307` (macOS, Ubuntu) the default is `home`, as before.
Explicit tool variables win in both modes.

make does not see a compiler change, so `compile.sh` records the GCC, TinyUSB and SDK paths it built
with in `<build>/.toolchain`; a build dir with another record (the other `BIG_MODULAR_TOOLCHAINS`
mode, a pinned version bump) or with objects and no record is removed with one `==> Stale build dir
...` line and built fresh (`opt/build-dir.sh`); an unchanged one builds incrementally.

Home lookup, pinned dependencies (first hit wins; `compile.sh` / `flash.sh` never download):

| Tool | Version | Looked up in |
|---|---|---|
| xPack `riscv-none-elf-gcc` | 15.2.0-1 | `$CH32_TOOLCHAIN`, `$CH32_HOME/xpack-riscv-none-elf-gcc-<v>`, PATH |
| TinyUSB | master `8d265ad1` (2026-11-04; 0.21.0 lacks the WCH USBHS ISO / connect fixes) | `$TINYUSB_PATH`, `$CH32_HOME/tinyusb-8d265ad1` |
| openwch/ch32v307 EVT | `184f21b8` (the commit TinyUSB pins) | `$WCH_SDK_PATH`, `$CH32_HOME/ch32v307-184f21b8` |
| wchisp | 0.3.0 | `$WCHISP_BIN`, PATH, `~/.cargo/bin`, `$CH32_HOME/wchisp-<v>` (os: `$WCHISP_BIN`, `$CH32_HOME/wchisp-<v>`, `/usr/bin`) |
| dfu-util | any | `$DFU_UTIL_BIN`, PATH (os: `/usr/bin/dfu-util`) |

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

On Azero OS (`/etc/azero-release`, see `opt/azero-os.sh`) the OS rules cover `4348:55e0` and the DFU IDs
`1209:0002` / `1209:0004`: `flash.sh` never uses `sudo`, a device it cannot open stops it with one line
(replug, or ask the operator), and `setup.sh` installs no rule.
Run the scripts as the checkout's owner (`azero` on Azero OS): any other user, root through `sudo`
included, is refused before anything runs (`opt/checkout-owner.sh`). Flashing from the operator's
SSH session: `azrun ./flash.sh ...` (until `azrun` is installed: `sudo -u azero -H bash -lc 'cd <dir>
&& ./flash.sh ...'`), never `sudo ./flash.sh`.
