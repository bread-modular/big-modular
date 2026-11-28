#!/usr/bin/env bash
#
# run.sh — instructions per sample of the master chain on the ESP32-S3.
#
# Builds this project and runs it in Espressif's QEMU with `-icount shift=0`
# (1 ns of virtual time per instruction). Needs qemu-system-xtensa on PATH:
#   python $IDF_PATH/tools/idf_tools.py install qemu-xtensa
# (it needs the system's libslirp0). QEMU counts instructions, not cycles: the
# real chip needs more than one cycle for some (loads, branches, FPU).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$HERE/../../../../../../opt/esp32-tools/common.sh"
activate_idf
check_idf_build_dir "$HERE" "$HERE/build"
command -v qemu-system-xtensa >/dev/null || die "qemu-system-xtensa not on PATH (see the header of this script)"

cd "$HERE"
idf.py build >/dev/null
(cd build && esptool.py --chip esp32s3 merge_bin --output qemu_flash.bin --fill-flash-size 2MB @flash_args >/dev/null)

echo "Calibration loop (the instructions from the 'loop' line to its end address are one pass):"
xtensa-esp32s3-elf-objdump -d build/ms_cpu_bench.elf --disassemble=app_main | grep -m1 -A4 "loop"

LOG="build/qemu.log"
: > "$LOG"
qemu-system-xtensa -nographic -M esp32s3 -m 4M \
  -drive file=build/qemu_flash.bin,if=mtd,format=raw \
  -icount shift=0 -serial file:"$LOG" -monitor none >/dev/null 2>&1 &
QEMU_PID=$!
trap 'kill "$QEMU_PID" 2>/dev/null; wait "$QEMU_PID" 2>/dev/null || true' EXIT
for _ in $(seq 300); do
  grep -aq "BENCH done" "$LOG" && break
  kill -0 "$QEMU_PID" 2>/dev/null || break
  sleep 1
done
grep -a "^BENCH" "$LOG" | grep -av "BENCH done" || die "no result (see $HERE/$LOG)"
