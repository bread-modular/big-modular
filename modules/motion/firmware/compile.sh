#!/usr/bin/env bash
#
# compile.sh — MOTION firmware wrapper around the shared opt/attiny1616-tools/compile.sh.
#
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export ATTINY_SKETCH_ROOT="$HERE"
exec "$HERE/../../../opt/attiny1616-tools/compile.sh"
