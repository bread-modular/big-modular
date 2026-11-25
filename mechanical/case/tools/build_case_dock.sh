#!/bin/sh
# Rebuild only the slide-in case dock. The original case stays unchanged.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
case_dir=$(dirname "$here")
fc=${FREECAD:-$HOME/Applications/FreeCAD_1.1.3.AppImage}
case "$fc" in *.AppImage) set -- "$fc" freecadcmd ;; *) set -- "$fc" ;; esac
research="$case_dir/research/case-dock"
mkdir -p "$research"
rm -f "$research/verification.json"
if ! CASE_DIR="$case_dir" "$@" "$here/build_case_dock.py" >"$research/build.log" 2>&1 ||
   grep -q 'Exception while processing' "$research/build.log" ||
   ! test -s "$research/verification.json"; then
    cat "$research/build.log" >&2
    exit 1
fi
cat "$research/verification.json"
