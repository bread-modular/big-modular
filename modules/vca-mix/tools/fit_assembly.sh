#!/bin/sh
# Nominal panel-over-carrier fit check. Run from anywhere; writes research/fit/ (ignored)
# and docs/fit/fit-report.json. Env: FREECAD (AppImage or freecadcmd path).
set -e
module=$(cd "$(dirname "$0")/.." && pwd)
fc=${FREECAD:-$HOME/Applications/FreeCAD_1.1.3.AppImage}
case "$fc" in *.AppImage) set -- "$fc" freecadcmd ;; *) set -- "$fc" ;; esac
fit=$module/research/fit
mkdir -p "$fit"
pcb=$module/hardware/vca-mix.kicad_pcb
step() { kicad-cli pcb export step -D KICAD10_3DMODEL_DIR=/usr/share/kicad/3dmodels \
  --user-origin 100x50mm --force "$@" >/dev/null; }
step --board-only -o "$fit/board.step" "$pcb"
step --no-board-body --component-filter 'U*,C*,R*,D*,J10' -o "$fit/back.step" "$pcb"
for ref in J1 J2 J3 J4 J5 J6 J7 J8 J9 J11; do
  step --no-board-body --component-filter "$ref" -o "$fit/$ref.step" "$pcb"
done
log=$fit/fit.log
"$@" "$module/tools/fit_assembly.py" >"$log" 2>&1 || true
# freecadcmd exits 0 even when the script raises, so check for its exception banner
if grep -q "^Exception while processing\|Traceback" "$log"; then
  grep -A8 "^Exception while processing\|Traceback" "$log" >&2
  exit 1
fi
cat "$module/docs/fit/fit-report.json"
