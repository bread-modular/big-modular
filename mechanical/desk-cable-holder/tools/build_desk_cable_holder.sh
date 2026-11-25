#!/bin/sh
# Build the desk cable holder with FreeCAD's headless interpreter (as mechanical/solder-arm/tools/build_solder_arm.sh).
# Env: FREECAD (path to a FreeCAD AppImage or freecadcmd).
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
holder_dir=$(dirname "$here")
fc=${FREECAD:-$HOME/Applications/FreeCAD_1.1.3.AppImage}
case "$fc" in *.AppImage) set -- "$fc" freecadcmd ;; *) set -- "$fc" ;; esac
research="$holder_dir/research"
mkdir -p "$research"
rm -f "$research/build-report.json" "$holder_dir/print/verification.json"
if ! HOLDER_DIR="$holder_dir" "$@" "$here/build_desk_cable_holder.py" >"$research/build.log" 2>&1; then
    grep -a -v '%)' "$research/build.log" | tail -40 >&2
    exit 1
fi
# freecadcmd exits 0 even when the script raises, so check for its exception banner
if grep -q 'Exception while processing' "$research/build.log" ||
   ! grep -q 'DESK_CABLE_HOLDER_BUILD_PASS' "$research/build.log" ||
   ! test -s "$research/build-report.json"; then
    grep -a -o 'Exception while processing.*' "$research/build.log" | sort -u >&2
    grep -a -v '%)' "$research/build.log" | tail -15 >&2
    exit 1
fi
python3 -B "$here/build_plates.py"
python3 -c "
import json,sys
r=json.load(open(sys.argv[1]))
print('desk cable holder', r['status'], '| seats', r['comb']['seats'], '| desks', r['dimensions']['desk_thickness_mm'],
      '| thread gap', r['thread']['gap_mm'], '| collisions', {k:v['collisions'] for k,v in r['desks'].items()},
      '| build', r['build_s'], 's')
" "$research/build-report.json"
