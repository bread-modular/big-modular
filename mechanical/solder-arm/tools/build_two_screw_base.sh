#!/bin/sh
# Build the retrofit only: DO NOT rerun the five original print plates.
set -eu
here=$(dirname "$(realpath "$0")")
work="$here/../research/two-screw-base"
mkdir -p "$work"
fc=${FREECAD:-$HOME/Applications/FreeCAD_1.1.3.AppImage}
case "$fc" in *.AppImage) set -- "$fc" freecadcmd ;; *) set -- "$fc" ;; esac
# FreeCADCmd can return zero after a Python exception; require this run's pass marker.
if ! "$@" "$here/build_two_screw_base.py" >"$work/build.log" 2>&1 ||
   ! grep -q 'TWO_SCREW_BASE_PASS' "$work/build.log" || grep -q 'Exception while processing' "$work/build.log"; then
    grep -a 'Exception while processing' "$work/build.log" >&2 || :
    exit 1
fi
printf '%s\n' 'TWO_SCREW_BASE_PASS'
