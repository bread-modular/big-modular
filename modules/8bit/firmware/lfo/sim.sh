#!/usr/bin/env bash
# ============================================================================
# Build & run the lfo firmware's host self-tests.
#
# No hardware, no arduino-cli — compiles the real rate/shape maths
# (lfo/LfoMath.h) and the MIDI clock sync (lfo/LfoSync.h) with plain c++
# and runs assertions on them.
#
# Usage:
#   ./sim.sh              # build + run all tests (exit 0 = pass)
#   CXX=g++ ./sim.sh      # pick a compiler explicitly
# ============================================================================
set -euo pipefail
cd "$(dirname "$0")"

CXX="${CXX:-c++}"
status=0
for test in test_lfo_math test_lfo_sync; do
  echo ">> building $test ($CXX)..."
  "$CXX" -std=c++11 -Wall -Wextra -Ilfo "sim/$test.cpp" -o "sim/$test"
  echo ">> running $test..."
  "sim/$test" || status=1
done
exit $status
