#!/usr/bin/env bash
# Host tests for the 12bit crash logic (src/crash_logic.h); no
# hardware. `./test.sh wav` also writes preview WAVs of the DAC output to
# .build/wav/ (a few knob settings and the knob sweeps), to listen on the PC.
# `./test.sh cal` measures the level tables again and rewrites
# src/crash_levels.h (after a change to the sound, or to the level of
# ../clapsnare, which it is matched to), then runs the tests.
set -euo pipefail
cd "$(dirname "$0")"
CXX="${CXX:-c++}"
mkdir -p .build
if [[ "${1:-}" == cal ]]; then
  "$CXX" -std=c++17 -O2 -Wall -Wextra -Isrc -I../clapsnare/src tools/calibrate.cpp -o .build/calibrate
  .build/calibrate src/crash_levels.h
fi
"$CXX" -std=c++17 -O2 -Wall -Wextra -Isrc -Itools -I../clapsnare/src test/test_logic.cpp -o .build/test_logic
if [[ "${1:-}" == wav ]]; then
  mkdir -p .build/wav
  .build/test_logic .build/wav
else
  .build/test_logic
fi
