#!/bin/sh
# Build the desk cable holder with FreeCAD's headless interpreter (as mechanical/solder-arm/tools/build_solder_arm.sh).
# Env: FREECAD (headless FreeCAD to run; default the OS freecadcmd, a FreeCAD AppImage also works).
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
holder_dir=$(dirname "$here")
fc=${FREECAD:-freecadcmd}
case "$fc" in *.AppImage) set -- "$fc" freecadcmd ;; *) set -- "$fc" ;; esac
research="$holder_dir/research"
mkdir -p "$research"
if ! HOLDER_DIR="$holder_dir" "$@" "$here/build_end_clips.py" >"$research/build.log" 2>&1 ||
   ! grep -q 'END_CLIPS_PASS' "$research/build.log" || grep -q 'Exception while processing' "$research/build.log"; then
    tr '\r' '\n' <"$research/build.log" | tail -20 >&2
    exit 1
fi
printf '%s\n' 'Carrier, end clips, screws and assembled fit: CAD_PASS'
