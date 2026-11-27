#!/bin/sh
# Build only the fused flat panels of the 2 x 2 case set, preserving original case exports.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
case_dir=$(dirname "$here")
fc=${FREECAD:-freecadcmd}
case "$fc" in *.AppImage) set -- "$fc" freecadcmd ;; *) set -- "$fc" ;; esac
research="$case_dir/research/quad-case"
mkdir -p "$research"
out="$case_dir/print/quad-case"
rm -f "$research/build-report.json" "$out/verification.json" "$out/mesh-verification.json"
if ! CASE_DIR="$case_dir" "$@" "$here/build_quad_case.py" >"$research/build.log" 2>&1; then
    cat "$research/build.log" >&2
    exit 1
fi
if grep -q 'Exception while processing' "$research/build.log" ||
   ! grep -q 'QUAD_CASE_BUILD_PASS' "$research/build.log" ||
   ! test -s "$research/build-report.json"; then
    cat "$research/build.log" >&2
    exit 1
fi
cat "$research/build-report.json"
