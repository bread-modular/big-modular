#!/bin/sh
# Build the 4MIX standoff 3D model with FreeCAD's headless interpreter (as mechanical/case/tools/build.sh).
# Env: FREECAD (headless FreeCAD to run; default the OS freecadcmd, a FreeCAD AppImage also works).
set -e
here=$(cd "$(dirname "$0")" && pwd)
fc=${FREECAD:-freecadcmd}
case "$fc" in *.AppImage) set -- "$fc" freecadcmd ;; *) set -- "$fc" ;; esac
log=$(dirname "$here")/research/standoff-build.log
mkdir -p "$(dirname "$log")"
MODULE_DIR=$(dirname "$here") "$@" "$here/build_standoff.py" >"$log" 2>&1 || true
# freecadcmd exits 0 even when the script raises, so check for its exception banner
if grep -q "^Exception while processing" "$log"; then
  grep -A3 "^Exception while processing" "$log" >&2
  exit 1
fi
grep "^standoff bbox" "$log"
