#!/bin/sh
# Build only the USB riser for modules/32bit; original case exports are kept.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
case_dir=$(dirname "$here")
fc=${FREECAD:-$HOME/Applications/FreeCAD_1.1.3.AppImage}
case "$fc" in *.AppImage) set -- "$fc" freecadcmd ;; *) set -- "$fc" ;; esac
research="$case_dir/research/usb-riser/final"
mkdir -p "$research"
out="$case_dir/print/accessories/usb-riser"
rm -f "$research/build-report.json" "$out/verification.json" "$out/mesh-verification.json"
if ! CASE_DIR="$case_dir" "$@" "$here/build_usb_riser.py" >"$research/build.log" 2>&1; then
    cat "$research/build.log" >&2
    exit 1
fi
if grep -q 'Exception while processing' "$research/build.log" ||
   ! grep -q 'USB_RISER_BUILD_PASS' "$research/build.log" ||
   ! test -s "$research/build-report.json"; then
    cat "$research/build.log" >&2
    exit 1
fi
cat "$research/build-report.json"
