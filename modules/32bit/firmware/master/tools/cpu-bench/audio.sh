#!/usr/bin/env bash
#
# audio.sh — the demo loop through the master chain on the emulated ESP32-S3.
#
# Builds the bench with two bars of ../demo.py's loop in its flash, runs it in
# Espressif's QEMU (the chip's instruction set and its single-precision FPU), and
# compares every output sample with the host render (../ms_render) of the same
# inputs and settings. The QEMU output is kept as WAV files to listen to:
#   <out>/qemu-factory.wav, qemu-glue.wav, qemu-glue-fast.wav  (host-*.wav beside them)
# Default <out>: modules/32bit/research/master/qemu (ignored). Needs
# qemu-system-xtensa on PATH, as run.sh. Not the codec, not cycle timing.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$HERE/../../../../../../opt/esp32-tools/common.sh"
OUT="${1:-$HERE/../../../../research/master/qemu}"
mkdir -p "$OUT"
OUT="$(cd "$OUT" && pwd)"
PYTHON="$(command -v python3)"  # the system's (numpy), not the ESP-IDF environment's
make -s -C "$HERE/.." ms_render
"$PYTHON" -B "$HERE/audio.py" prepare --out "$OUT" --header "$HERE/main/audio_in.h"

activate_idf
check_idf_build_dir "$HERE" "$HERE/build-audio"
command -v qemu-system-xtensa >/dev/null || die "qemu-system-xtensa not on PATH (see the header of run.sh)"

cd "$HERE"
idf.py -B build-audio -DMS_BENCH_AUDIO=1 build >/dev/null
(cd build-audio && esptool.py --chip esp32s3 merge_bin --output qemu_flash.bin --fill-flash-size 2MB @flash_args >/dev/null)

LOG="build-audio/qemu.log"
: > "$LOG"
qemu-system-xtensa -nographic -M esp32s3 -m 4M \
  -drive file=build-audio/qemu_flash.bin,if=mtd,format=raw \
  -icount shift=0 -serial file:"$LOG" -monitor none >/dev/null 2>&1 &
QEMU_PID=$!
trap 'kill "$QEMU_PID" 2>/dev/null; wait "$QEMU_PID" 2>/dev/null || true' EXIT
for _ in $(seq 900); do
  grep -aq "BENCH done" "$LOG" && break
  kill -0 "$QEMU_PID" 2>/dev/null || break
  sleep 1
done
grep -aq "BENCH done" "$LOG" || die "no result (see $HERE/$LOG)"
"$PYTHON" -B "$HERE/audio.py" compare --out "$OUT" --log "$LOG" --render "$HERE/../ms_render"
echo "WAV files in $OUT"
