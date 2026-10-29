#!/usr/bin/env bash
# ============================================================================
# Build & run the shared CvRecorder host self-tests (no hardware, no
# arduino-cli).
#
# Usage:
#   ./sim.sh              # build + run all tests (exit 0 = pass)
#   CXX=g++ ./sim.sh      # pick a compiler explicitly
# ============================================================================
set -euo pipefail
cd "$(dirname "$0")"

CXX="${CXX:-c++}"
SRC="sim/test_cv_recorder.cpp"
BIN="sim/test_cv_recorder"

echo ">> building host simulator ($CXX)..."
"$CXX" -std=c++11 -Wall -Wextra -Isim "$SRC" -o "$BIN"

echo ">> running tests..."
"$BIN"
