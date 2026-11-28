#!/usr/bin/env bash
# azero-os.sh — Azero OS detection for the opt/*-tools flash and setup scripts
# (sourced, not run).
#
# Azero OS gives its user no sudo and ships the udev rules for every probe and
# bootloader these scripts open (63-azero-flash.rules: the USB nodes and the
# serial ports belong to the uucp group). There the scripts never call sudo and
# never install udev rules or change groups; a device they cannot open is
# reported in one line. Detected by the OS's release file, the way
# /opt/big-modular/<family> selects the OS toolchains in each common.sh.
# Elsewhere (Ubuntu, macOS) nothing changes.

AZERO_OS_RELEASE=/etc/azero-release

azero_os() {
  [[ -f "$AZERO_OS_RELEASE" ]]
}

# Azero OS only: one line on stderr and status 1 when USB device vid[:pid] is on
# the bus but none of its nodes is read/writable by this user. Status 0 when one
# is, when none is attached (the flash tool reports that) and on other hosts.
azero_usb_access() { # vid[:pid]
  local vid="${1%%:*}" pid="" dev node found=()
  [[ "$1" != *:* ]] || pid="${1##*:}"
  azero_os || return 0
  for dev in /sys/bus/usb/devices/*; do
    [[ -f "$dev/idVendor" && -f "$dev/busnum" && -f "$dev/devnum" ]] || continue
    [[ "$(<"$dev/idVendor")" == "$vid" ]] || continue
    [[ -z "$pid" || "$(<"$dev/idProduct")" == "$pid" ]] || continue
    node="$(printf '/dev/bus/usb/%03d/%03d' "$(<"$dev/busnum")" "$(<"$dev/devnum")")"
    [[ -r "$node" && -w "$node" ]] && return 0
    found+=("$vid:$(<"$dev/idProduct") ($node)")
  done
  [[ ${#found[@]} -gt 0 ]] || return 0
  echo "Error: USB device ${found[*]} is not accessible to $(id -un); the Azero OS udev rules (63-azero-flash.rules, group uucp) should cover it: replug it, or ask the operator (no sudo on Azero OS)." >&2
  return 1
}
