#!/usr/bin/env bash
# checkout-owner.sh — wrong-user guard for the firmware compile / flash /
# package scripts (sourced, not run; shared like opt/azero-os.sh).
#
# The scripts write into the checkout (build dirs, caches) and open the board's
# USB / serial devices as the user who runs them. Run by another user they fail
# half-way (Permission denied on .build, on /dev/ttyUSB0); run with sudo they
# leave root-owned files in the build dirs and run, as root, files the owner can
# write (forbidden on Azero OS). require_checkout_owner stops first and says
# to log in as the owner (`azero` on Azero OS, e.g. ssh azero@azero2.local)
# and run the script there. Where a user owns and runs their own checkout
# (macOS, Ubuntu, azero itself) nothing changes. There is deliberately no
# override for root.

CHECKOUT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Owner uid / name of a path (GNU stat, else BSD stat on macOS).
checkout_owner_uid() {
  stat -c %u "$1" 2>/dev/null || stat -f %u "$1"
}
checkout_owner_name() {
  stat -c %U "$1" 2>/dev/null || stat -f %Su "$1"
}

# Exit 1 with one line on stderr unless the effective user owns the checkout.
# Callers pass "$@"; the arguments are not used.
require_checkout_owner() {
  local owner_uid owner host
  owner_uid="$(checkout_owner_uid "$CHECKOUT_ROOT")" || return 0
  [[ "$(id -u)" != "$owner_uid" ]] || return 0
  owner="$(checkout_owner_name "$CHECKOUT_ROOT")"
  host="$(hostname 2>/dev/null || uname -n)"
  echo "This checkout belongs to $owner. Log in as $owner and run it there (ssh $owner@${host%%.*}.local); never run it with sudo." >&2
  exit 1
}
