#!/bin/sh
# Build the soldering arm with FreeCAD's headless interpreter (as mechanical/case/tools/build.sh).
# Env: FREECAD (path to a FreeCAD AppImage or freecadcmd).
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
arm_dir=$(dirname "$here")
fc=${FREECAD:-$HOME/Applications/FreeCAD_1.1.3.AppImage}
case "$fc" in *.AppImage) set -- "$fc" freecadcmd ;; *) set -- "$fc" ;; esac
research="$arm_dir/research"
mkdir -p "$research"
rm -f "$research/build-report.json" "$arm_dir/print/verification.json"
if ! ARM_DIR="$arm_dir" "$@" "$here/build_solder_arm.py" >"$research/build.log" 2>&1; then
    grep -a -v '%)' "$research/build.log" | tail -40 >&2
    exit 1
fi
# freecadcmd exits 0 even when the script raises, so check for its exception banner
if grep -q 'Exception while processing' "$research/build.log" ||
   ! grep -q 'SOLDER_ARM_BUILD_PASS' "$research/build.log" ||
   ! test -s "$research/build-report.json"; then
    grep -a -o 'Exception while processing.*' "$research/build.log" | sort -u >&2
    exit 1
fi
python3 -B "$here/build_plates.py"
python3 -c "
import json,sys
r=json.load(open(sys.argv[1]))
print('solder arm', r['status'], '| jaw opening', r['dimensions']['jaw_opening_mm'], '| boards', r['boards']['scanned'],
      '| poses', {k:v['collisions'] for k,v in r['poses'].items()}, '| head sweep gap', r['head_sweep']['smallest_gap_to_desk_base_bracket_mm'],
      '| build', r['build_s'], 's')
" "$research/build-report.json"
