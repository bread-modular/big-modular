#!/bin/sh
# Rebuild only the add-on four-rail brace, never the original frame/case parts.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
case_dir=$(dirname "$here")
fc=${FREECAD:-$HOME/Applications/FreeCAD_1.1.3.AppImage}
case "$fc" in *.AppImage) set -- "$fc" freecadcmd ;; *) set -- "$fc" ;; esac
research="$case_dir/research/middle-brace"
out="$case_dir/print/side panels/middle-frame/top-brace"
mkdir -p "$research"
rm -f "$research/build-report.json" "$out/verification.json" "$out/mesh-verification.json"
if ! CASE_DIR="$case_dir" "$@" "$here/build_middle_brace.py" >"$research/build.log" 2>&1; then
    cat "$research/build.log" >&2
    exit 1
fi
if grep -q 'Exception while processing' "$research/build.log" ||
   ! grep -q 'MIDDLE_BRACE_BUILD_PASS' "$research/build.log" ||
   ! test -s "$research/build-report.json"; then
    cat "$research/build.log" >&2
    exit 1
fi
cat "$research/build-report.json"
