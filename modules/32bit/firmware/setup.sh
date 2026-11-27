#!/usr/bin/env bash
#
# setup.sh — one-time ESP-IDF setup (azero: checks the OS packages; elsewhere
# reuses an installed ~/esp/esp-idf v5.5.1 and ~/.espressif toolchain and
# downloads only on a machine without them).
#
set -euo pipefail

exec "$(dirname "${BASH_SOURCE[0]}")/../../../opt/esp32-tools/setup.sh" "$@"
