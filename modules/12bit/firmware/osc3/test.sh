#!/usr/bin/env bash
# Host tests for the 12bit osc3 logic (src/osc3_logic.h); no hardware.
set -euo pipefail
cd "$(dirname "$0")"
CXX="${CXX:-c++}"
mkdir -p .build
"$CXX" -std=c++17 -Wall -Wextra -Isrc test/test_logic.cpp -o .build/test_logic
.build/test_logic
