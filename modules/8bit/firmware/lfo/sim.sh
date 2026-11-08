#!/usr/bin/env bash
# ============================================================================
# Build & run the lfo firmware's host self-tests.
#
# No hardware, no arduino-cli — compiles the real rate/shape maths
# (lfo/LfoMath.h) with plain c++ and runs assertions on it.
#
# Usage:
#   ./sim.sh              # build + run all tests (exit 0 = pass)
#   CXX=g++ ./sim.sh      # pick a compiler explicitly
# ============================================================================
set -euo pipefail
cd "$(dirname "$0")"

CXX="${CXX:-c++}"
SRC="sim/test_lfo_math.cpp"
BIN="sim/test_lfo_math"

echo ">> building host simulator ($CXX)..."
"$CXX" -std=c++11 -Wall -Wextra -Ilfo "$SRC" -o "$BIN"

echo ">> running tests..."
"$BIN"
