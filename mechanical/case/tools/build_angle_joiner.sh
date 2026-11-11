#!/bin/sh
# Build only the bolt-on angled joiner variant, preserving original case exports.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
case_dir=$(dirname "$here")
fc=${FREECAD:-$HOME/Applications/FreeCAD_1.1.3.AppImage}
case "$fc" in *.AppImage) set -- "$fc" freecadcmd ;; *) set -- "$fc" ;; esac
research="$case_dir/research/angle-joiner"
mkdir -p "$research"
out="$case_dir/print/side panels/angle-joiner"
rm -f "$research/build-report.json" "$out/verification.json" "$out/mesh-verification.json"
if ! CASE_DIR="$case_dir" "$@" "$here/build_angle_joiner.py" >"$research/build.log" 2>&1; then
    cat "$research/build.log" >&2
    exit 1
fi
if grep -q 'Exception while processing' "$research/build.log" ||
   ! grep -q 'ANGLE_JOINER_BUILD_PASS' "$research/build.log" ||
   ! test -s "$research/build-report.json"; then
    cat "$research/build.log" >&2
    exit 1
fi
cat "$research/build-report.json"
