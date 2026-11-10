#!/bin/sh
# Build only the shared middle frame. Existing case geometry is read, never overwritten.
# FREECAD may name freecadcmd or the project's FreeCAD AppImage.
# JOINER_RAIL_CLEARANCE changes the prototype socket allowance (mm per face).
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
case_dir=$(dirname "$here")
fc=${FREECAD:-$HOME/Applications/FreeCAD_1.1.3.AppImage}
case "$fc" in *.AppImage) set -- "$fc" freecadcmd ;; *) set -- "$fc" ;; esac
research="$case_dir/research/middle-frame"
mkdir -p "$research"
rm -f "$research/build-report.json"
if ! CASE_DIR="$case_dir" "$@" "$here/build_middle_frame.py" >"$research/build.log" 2>&1; then
    cat "$research/build.log" >&2
    exit 1
fi
if grep -q 'Exception while processing' "$research/build.log" ||
   ! grep -q 'MIDDLE_FRAME_BUILD_PASS' "$research/build.log" ||
   ! test -s "$research/build-report.json"; then
    cat "$research/build.log" >&2
    exit 1
fi
cat "$research/build-report.json"
