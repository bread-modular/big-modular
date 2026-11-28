#!/usr/bin/env bash
# checkout-owner.sh — wrong-user guard for the firmware compile / flash /
# package scripts (sourced, not run; shared like opt/azero-os.sh).
#
# The scripts write into the checkout (build dirs, caches) and open the board's
# USB / serial devices as the user who runs them. Run by another user they fail
# half-way (Permission denied on .build, on /dev/ttyUSB0); run with sudo they
# leave root-owned files in the build dirs and run, as root, files the owner can
# write (forbidden on Azero OS). require_checkout_owner stops first, with the
# command to use instead: on Azero OS the operator account runs them as the
# owner with `azrun` (or `sudo -u <owner>` where azrun is not installed yet).
# Where a user owns and runs their own checkout (macOS, Ubuntu, azero itself)
# nothing changes. There is deliberately no override for root.

CHECKOUT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Owner uid / name of a path (GNU stat, else BSD stat on macOS).
checkout_owner_uid() {
  stat -c %u "$1" 2>/dev/null || stat -f %u "$1"
}
checkout_owner_name() {
  stat -c %U "$1" 2>/dev/null || stat -f %Su "$1"
}

# Exit 1 with one line on stderr unless the effective user owns the checkout.
# Pass the entry script's arguments ("$@") for the suggested command.
require_checkout_owner() {
  local owner_uid owner cmd inner
  owner_uid="$(checkout_owner_uid "$CHECKOUT_ROOT")" || return 0
  [[ "$(id -u)" != "$owner_uid" ]] || return 0
  owner="$(checkout_owner_name "$CHECKOUT_ROOT")"
  cmd="$(printf '%q ' "$0" "$@")"
  cmd="${cmd% }"
  if command -v azrun >/dev/null 2>&1; then
    echo "This checkout belongs to $owner. Run it as $owner: azrun $cmd   (never with sudo)" >&2
  else
    inner="cd $(printf '%q' "$PWD") && $cmd"
    inner="${inner//\'/\'\\\'\'}"
    echo "This checkout belongs to $owner. Run it as $owner: sudo -u $owner -H bash -lc '$inner'   (never as root)" >&2
  fi
  exit 1
}
