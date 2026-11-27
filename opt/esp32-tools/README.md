# esp32-tools

Shared ESP32-S3 (ESP-IDF) build scripts for the modules' firmwares, the
counterpart of `opt/attiny1616-tools`. Based on Bread Modular `opt/esp32-tools`
(macOS-only there); this copy also handles Linux serial ports and reuses an
installed ESP-IDF without downloading.

| Script | Use |
|---|---|
| `setup.sh` | reuse ESP-IDF ($IDF_PATH / $IDF_DIR / `~/esp/esp-idf`) and `~/.espressif` tools if they activate; otherwise clone v5.5.1 + `install.sh esp32s3`; OS packages: check only |
| `compile.sh` | `idf.py build` in `$ESP32_PROJECT_ROOT` |
| `flash.sh [port]` | build + flash; picks `/dev/ttyACM*` / `/dev/ttyUSB*` (Linux) or `/dev/cu.usbmodem*` (macOS); `MONITOR=1` opens the monitor |
| `common.sh` | sourced helpers |

Module wrappers set `ESP32_PROJECT_ROOT` (the ESP-IDF project) and
`ESP32_DEFINES` (space-separated `KEY=VALUE`, passed as `idf.py -D`), e.g.
`modules/32bit/firmware/jumper.sh`. Defaults: `IDF_VERSION=v5.5.1`,
`IDF_TARGET=esp32s3`.

## OS toolchains (azero) and the home fallback

Where `/opt/big-modular/esp32` exists (azero's OS packages) the scripts default
to `BIG_MODULAR_TOOLCHAINS=os`: ESP-IDF v5.5.1 from `/opt/big-modular/esp32/esp-idf` (release zip, no `.git`: the version comes from `version.txt`) with its tools and Python environment in `IDF_TOOLS_PATH` = `/opt/big-modular/esp32/espressif`, `/usr/bin` first on the PATH (Arch's `cmake` 4.5 and `ninja`). Home lookup: `$IDF_PATH`, `$IDF_DIR`, `~/esp/esp-idf`, `~/esp/esp-idf-<version>` with `~/.espressif`. They are resolved by explicit path, so
a home copy earlier on the PATH (`~/.local/bin`, `~/bin`, `~/.cargo/bin`) is
never picked, in any shell, login or not (the `/etc/profile.d/big-modular-*.sh`
variables are not needed). `setup.sh` then only checks: nothing is downloaded
or written. `BIG_MODULAR_TOOLCHAINS=home` restores the home lookup below
(`/opt/big-modular` values exported by `/etc/profile.d` are ignored). Without
`/opt/big-modular/esp32` (macOS, Ubuntu) the default is `home`, as before.
Explicit tool variables win in both modes.
