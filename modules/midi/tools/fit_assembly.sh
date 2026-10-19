#!/bin/sh
# Nominal panel-over-carrier fit check: tools/fit_assembly.sh v1|v2. Run from anywhere; writes
# research/<version>/fit/ (ignored) and the version's fit-report.json (docs/fit/ for V1,
# docs/v2/fit/ for V2). Env: FREECAD (AppImage or freecadcmd path).
set -e
module=$(cd "$(dirname "$0")/.." && pwd)
case "$1" in v1|v2) MIDI_VERSION=$1 ;; *) echo "usage: $0 v1|v2" >&2; exit 2 ;; esac
export MIDI_VERSION
report=$module/docs/fit/fit-report.json
[ "$MIDI_VERSION" = v1 ] || report=$module/docs/$MIDI_VERSION/fit/fit-report.json
fc=${FREECAD:-$HOME/Applications/FreeCAD_1.1.3.AppImage}
case "$fc" in *.AppImage) set -- "$fc" freecadcmd ;; *) set -- "$fc" ;; esac
fit=$module/research/$MIDI_VERSION/fit
mkdir -p "$fit"
pcb=$module/hardware/$MIDI_VERSION/midi.kicad_pcb
step() { kicad-cli pcb export step -D KICAD10_3DMODEL_DIR=/usr/share/kicad/3dmodels \
  --user-origin 100x50mm --force "$@" >/dev/null; }
step --board-only -o "$fit/board.step" "$pcb"
step --no-board-body --component-filter 'U*,C*,R*,Q*,D9,D10,D11,D12,D13,D14,D15,D16,D17,D18,JP*,J10,J11' -o "$fit/back.step" "$pcb"
for ref in J1 J2 J3 J4 J5 J6 J7 J8 J9 D1 D2 D3 D4 D5 D6 D7 D8; do
  step --no-board-body --component-filter "$ref" -o "$fit/$ref.step" "$pcb"
done
log=$fit/fit.log
"$@" "$module/tools/fit_assembly.py" >"$log" 2>&1 || true
# freecadcmd exits 0 even when the script raises, so check for its exception banner
if grep -q "^Exception while processing\|Traceback" "$log"; then
  grep -A8 "^Exception while processing\|Traceback" "$log" >&2
  exit 1
fi
cat "$report"
