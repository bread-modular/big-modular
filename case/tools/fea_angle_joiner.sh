#!/bin/sh
# Static screening of the angle-joiner cheek; see fea_angle_joiner.py for the model and limits.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
case_dir=$(dirname "$here")
fc=${FREECAD:-$HOME/Applications/FreeCAD_1.1.3.AppImage}
case "$fc" in *.AppImage) set -- "$fc" freecadcmd ;; *) set -- "$fc" ;; esac
# Cap the memory, so a runaway solve stops instead of taking the machine down.
if command -v systemd-run >/dev/null 2>&1 && systemd-run --user --scope -q true 2>/dev/null; then
    set -- systemd-run --user --scope -q -p MemoryMax="${JOINER_FEA_MEM:-16G}" -p MemorySwapMax=0 "$@"
fi
research="$case_dir/research/angle-joiner/fea"
mkdir -p "$research"
if ! CASE_DIR="$case_dir" "$@" "$here/fea_angle_joiner.py" >"$research/run.log" 2>&1 ||
   grep -q 'Exception while processing' "$research/run.log" ||
   ! grep -q 'ANGLE_JOINER_FEA_DONE' "$research/run.log"; then
    cat "$research/run.log" >&2
    exit 1
fi
grep '^ANGLE_JOINER_FEA_DONE' "$research/run.log"
