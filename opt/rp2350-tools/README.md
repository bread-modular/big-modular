# rp2350-tools

Shared RP2350 (Pico SDK) build scripts for the modules' firmwares, the
counterpart of `opt/esp32-tools` and `opt/attiny1616-tools`. Based on the
Bread Modular 16bit `scripts/` (macOS-only there); this copy also runs on Linux
and reuses installed tools without downloading.

| Script | Use |
|---|---|
| `setup.sh` | reuse the Pico SDK / ARM toolchain / picotool / cmake / ninja if found; otherwise install the Bread Modular versions under `~/.breadmodular` (Linux x86_64/aarch64, macOS) |
| `compile.sh` | cmake configure + build `$RP2350_TARGET` in `$RP2350_PROJECT_ROOT` -> `<build>/<target>.uf2` |
| `flash.sh [fw.uf2]` | build (unless a UF2 is given), print the UF2 program name / version / description, then `picotool load -f`; if that fails, reboots the running board into BOOTSEL with a 1200 baud open of its USB serial port (`RP2350_SERIAL_PORT` to pick one) and copies onto the RP2350 drive (`udisksctl` mount on Linux) |
| `flash.sh info` | show the program name / version / description of the firmware on the board (`picotool info -f`) |
| `common.sh` | sourced helpers |

Tool lookup (first hit wins, nothing is downloaded by `compile.sh` / `flash.sh`):

| Tool | Version | Looked up in |
|---|---|---|
| Pico SDK (+ `lib/tinyusb`) | 2.1.1 | `$PICO_SDK_PATH`, `~/.breadmodular/pico-sdk/sdk/2.1.1`, `~/.pico-sdk/sdk/2.1.1` |
| ARM GNU toolchain | 14.2.rel1 | `$PICO_TOOLCHAIN_PATH`, `~/.breadmodular/toolchain/14_2_Rel1`, `~/.pico-sdk/toolchain/14_2_Rel1`, `arm-none-eabi-gcc` on the PATH |
| picotool | 2.2.0-a4 | `$PICOTOOL_BIN`, `~/.breadmodular/picotool/2.2.0-a4/picotool/picotool`, `~/.pico-sdk/picotool/*`, PATH |
| cmake (>= 3.13), ninja | any | `$CMAKE_BIN` / `$NINJA_BIN`, PATH, `~/.breadmodular/bin` |

`~/.breadmodular` (`$BREADMODULAR_HOME`) is the Bread Modular tool home, so a
machine that already builds the BM 16bit firmware shares that install. The
build passes picotool's CMake package to the SDK (`picotool_DIR`), so a fresh
build dir does not fetch and build picotool from source.

Module wrappers set `RP2350_PROJECT_ROOT` (the CMake project),
`RP2350_TARGET` (target / UF2 name, default the project dir name),
`RP2350_DEFINES` (space-separated `KEY=VALUE`, passed as `cmake -D`) and
optionally `RP2350_BUILD_DIR` (default `<project>/.build`), e.g.
`modules/16bit/firmware/jumper.sh`.

## Linux USB access

picotool talks to the RP2350 over libusb and needs root without a udev rule
for the Raspberry Pi vendor ID (`setup.sh` prints a note when none is
installed). One-time:

```sh
echo 'SUBSYSTEM=="usb", ATTRS{idVendor}=="2e8a", MODE="0660", TAG+="uaccess"' | \
  sudo tee /etc/udev/rules.d/99-picotool.rules
sudo udevadm control --reload-rules && sudo udevadm trigger
```

Without it, `flash.sh` reboots a running board into BOOTSEL through its serial
port (1200 baud; needs the `dialout` group) and copies the UF2 onto the
`RP2350` drive. A blank or crashed board: hold BOOT, tap RESET, release BOOT.
