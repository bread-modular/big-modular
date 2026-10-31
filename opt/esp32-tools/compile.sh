#!/usr/bin/env bash
# compile.sh — build an ESP32-S3 ESP-IDF project (see common.sh for the env).
set -euo pipefail

TOOLS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$TOOLS_DIR/common.sh"

resolve_project
activate_idf

echo "==> Building $PROJECT_DIR (target: $IDF_TARGET${ESP32_DEFINES:+, $ESP32_DEFINES})"
cd "$PROJECT_DIR"
idf.py "${IDF_DEFINE_ARGS[@]+"${IDF_DEFINE_ARGS[@]}"}" build

echo "✅ Build complete: $PROJECT_DIR/build"
