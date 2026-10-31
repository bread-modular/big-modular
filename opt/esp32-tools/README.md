# esp32-tools

Shared ESP32-S3 (ESP-IDF) build scripts for the modules' firmwares, the
counterpart of `opt/attiny1616-tools`. Based on Bread Modular `opt/esp32-tools`
(macOS-only there); this copy also handles Linux serial ports and reuses an
installed ESP-IDF without downloading.

| Script | Use |
|---|---|
| `setup.sh` | reuse ESP-IDF ($IDF_PATH / $IDF_DIR / `~/esp/esp-idf`) and `~/.espressif` tools if they activate; otherwise clone v5.5.1 + `install.sh esp32s3` |
| `compile.sh` | `idf.py build` in `$ESP32_PROJECT_ROOT` |
| `flash.sh [port]` | build + flash; picks `/dev/ttyACM*` / `/dev/ttyUSB*` (Linux) or `/dev/cu.usbmodem*` (macOS); `MONITOR=1` opens the monitor |
| `common.sh` | sourced helpers |

Module wrappers set `ESP32_PROJECT_ROOT` (the ESP-IDF project) and
`ESP32_DEFINES` (space-separated `KEY=VALUE`, passed as `idf.py -D`), e.g.
`modules/32bit/firmware/jumper.sh`. Defaults: `IDF_VERSION=v5.5.1`,
`IDF_TARGET=esp32s3`.
