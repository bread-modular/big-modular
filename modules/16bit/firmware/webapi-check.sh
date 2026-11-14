#!/usr/bin/env bash
#
# webapi-check.sh — check that a built 16bit firmware still answers the
# breadmodular.com/ui/16bit Web Serial UI (bread-modular-website
# app/ui/16bit + app/lib/webserial.ts, commit f991473).
#
# The UI opens the USB CDC port at 115200, sends "get-app", reads the
# "::val::<app>::val::" reply and then uses the commands of that app. This
# script looks for those command strings, the reply format and the USB
# strings in the ELF, so a firmware change that drops one fails the build.
#
# Usage:
#   ./webapi-check.sh <app> [elf]    # elf default: 16bit/.build/16bit.elf
#
set -euo pipefail

FW_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP="${1:-}"
ELF="${2:-$FW_DIR/16bit/.build/16bit.elf}"
[[ -n "$APP" ]] || { echo "Usage: ./webapi-check.sh <app> [elf]" >&2; exit 1; }
[[ -f "$ELF" ]] || { echo "No ELF at $ELF (build first)" >&2; exit 1; }

# Every app: app query, value reply format, app name, USB identity.
NEED=(get-app "::val::%s::val::" "$APP" "Bread Modular" 16bit)
case "$APP" in
  sampler)   NEED+=(get-fx set-fx play-sample "write-sample-base64 ") ;;
  polysynth) ;;  # set-/get-waveform dropped: P2 picks the BM waveform
  fxrack)    NEED+=(get-fx set-fx) ;;
  elab)      NEED+=(get-scope-channels start-send start-send-2 stop-send) ;;
  monosynth|noop|lyra4) ;;  # UI only shows the app; no serial state
  *) echo "Unknown app '$APP'" >&2; exit 1 ;;
esac

STRINGS="$(strings -a -n 4 "$ELF")"
missing=0
for s in "${NEED[@]}"; do
  if ! grep -qF -- "$s" <<< "$STRINGS"; then
    echo "  MISSING web API string for $APP: '$s'" >&2
    missing=$((missing + 1))
  fi
done
if [[ "$missing" -ne 0 ]]; then
  echo "==> Web API check FAILED for $APP ($missing missing)" >&2
  exit 1
fi
echo "==> Web API check OK for $APP (${#NEED[@]} strings)"
