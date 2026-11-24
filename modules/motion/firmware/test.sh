#!/usr/bin/env bash
#
# test.sh — build and run the MOTION recorder host test (no hardware, no
# arduino-cli). Exit 0 = pass.
#
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

CXX="${CXX:-c++}"
OUT="$(mktemp -d "${TMPDIR:-/tmp}/motion-sim.XXXXXX")"
trap 'rm -rf "$OUT"' EXIT

"$CXX" -std=c++11 -O1 -Wall -Wextra -Werror -fsanitize=address,undefined \
  -Imotion tools/sim_motion.cpp -o "$OUT/sim_motion"
"$OUT/sim_motion"
