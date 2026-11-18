#!/bin/sh
# Build the two-piece push-button cap with FreeCAD's headless interpreter, then its section drawing.
# Env: FREECAD (path to a FreeCAD AppImage or freecadcmd).
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cap_dir=$(dirname "$here")
fc=${FREECAD:-$HOME/Applications/FreeCAD_1.1.3.AppImage}
case "$fc" in *.AppImage) set -- "$fc" freecadcmd ;; *) set -- "$fc" ;; esac
mkdir -p "$cap_dir/research"
log="$cap_dir/research/build.log"
"$@" "$here/build_button_cap.py" >"$log" 2>&1 || true
# freecadcmd exits 0 even when the script raises, so check for the pass marker
if ! grep -q 'BUTTON_CAP_BUILD_PASS' "$log"; then
    tail -20 "$log" >&2
    exit 1
fi
grep -a -B4 'BUTTON_CAP_BUILD_PASS' "$log"
python3 -B "$here/render_section.py"
