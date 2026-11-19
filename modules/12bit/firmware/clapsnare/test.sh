#!/usr/bin/env bash
# Host tests for the 12bit clapsnare logic (src/clapsnare_logic.h); no
# hardware. `./test.sh wav` also writes preview WAVs of the DAC output to
# .build/wav/ (a few knob settings and one knob sweep), to listen on the PC.
set -euo pipefail
cd "$(dirname "$0")"
CXX="${CXX:-c++}"
mkdir -p .build
"$CXX" -std=c++17 -O2 -Wall -Wextra -Isrc test/test_logic.cpp -o .build/test_logic
if [[ "${1:-}" == wav ]]; then
  mkdir -p .build/wav
  .build/test_logic .build/wav
else
  .build/test_logic
fi
