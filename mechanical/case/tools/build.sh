#!/bin/sh
# Build the skiff with FreeCAD's headless interpreter. Env: CASE_HP, CASE_DEPTH, CASE_ROW_GAP,
# FREECAD (path to FreeCAD AppImage or freecadcmd).
set -e
here=$(cd "$(dirname "$0")" && pwd)
fc=${FREECAD:-$HOME/Applications/FreeCAD_1.1.3.AppImage}
case "$fc" in *.AppImage) set -- "$fc" freecadcmd ;; *) set -- "$fc" ;; esac
log=$(dirname "$here")/research/build.log
mkdir -p "$(dirname "$log")"
CASE_DIR=$(dirname "$here") "$@" "$here/build_case.py" >"$log" 2>&1 || true
# freecadcmd exits 0 even when the script raises, so check for its exception banner
if grep -q "^Exception while processing" "$log"; then
  grep -A3 "^Exception while processing" "$log" >&2
  exit 1
fi
cat "$(dirname "$here")/research/build-report.json"
