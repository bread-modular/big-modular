#!/bin/sh
# Build the RV09 push-on knobs with FreeCAD's headless interpreter (as mechanical/case/tools/build.sh).
# Env: FREECAD (path to FreeCAD AppImage or freecadcmd).
set -e
here=$(cd "$(dirname "$0")" && pwd)
fc=${FREECAD:-$HOME/Applications/FreeCAD_1.1.3.AppImage}
case "$fc" in *.AppImage) set -- "$fc" freecadcmd ;; *) set -- "$fc" ;; esac
log=$(dirname "$here")/research/build.log
mkdir -p "$(dirname "$log")"
KNOB_DIR=$(dirname "$here") "$@" "$here/build_knobs.py" >"$log" 2>&1 || true
# freecadcmd exits 0 even when the script raises, so check for its exception banner
if grep -q "^Exception while processing" "$log"; then
  grep -A3 "^Exception while processing" "$log" >&2
  exit 1
fi
grep "^knob report" "$log"
