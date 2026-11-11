#!/bin/sh
# Build the stand. Env: STAND_TILTS (deg, e.g. 0,40,70; the first must be 0, row 1 lies flat on the tier 1 ledges), STAND_TIERS (2 or 3),
# FREECAD (path to FreeCAD AppImage or freecadcmd).
set -e
here=$(cd "$(dirname "$0")" && pwd)
fc=${FREECAD:-$HOME/Applications/FreeCAD_1.1.3.AppImage}
case "$fc" in *.AppImage) set -- "$fc" freecadcmd ;; *) set -- "$fc" ;; esac
log=$(dirname "$here")/research/stand.log
mkdir -p "$(dirname "$log")"
CASE_DIR=$(dirname "$here") "$@" "$here/build_stand.py" >"$log" 2>&1 || true
# freecadcmd exits 0 even when the script raises, so check for its exception banner
if grep -q "^Exception while processing" "$log"; then
  grep -A3 "^Exception while processing" "$log" >&2
  exit 1
fi
cat "$(dirname "$here")/research/stand/stand-${STAND_TIERS:-3}-report.json"
