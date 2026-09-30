#!/usr/bin/env bash
# SCRIPT: list-devices
# DESCRIPTION: List paired InkMate device IDs and detected USB serial ports
# USAGE: ./scripts/list-devices.sh
# PARAMETERS:
#   None
# EXAMPLE: ./dev devices list
# ----------------------------------------------------
set -euo pipefail

if [[ ${1:-} == -h || ${1:-} == --help ]]; then
  sed -n '/^# SCRIPT:/,/^# ----------------------------------------------------/s/^# \{0,1\}//p' "$0"
  exit 0
fi

[[ $# -eq 0 ]] || { echo "usage: $0" >&2; exit 2; }

repo_dir=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
env_file="$repo_dir/.env"

echo "Paired device IDs:"
if [[ -f "$env_file" ]]; then
  entries=$(sed -n 's/^INKMATE_DEVICE_SECRETS=//p' "$env_file" | tail -1)
  if [[ -n "$entries" ]]; then
    IFS=',' read -r -a device_entries <<< "$entries"
    for entry in "${device_entries[@]}"; do
      printf '  %s\n' "${entry%%:*}"
    done
  else
    echo "  none configured"
  fi
else
  echo "  none configured (.env is missing)"
fi

echo
echo "Detected USB serial ports:"
shopt -s nullglob
ports=(/dev/ttyACM* /dev/ttyUSB* /dev/cu.usb*)
if [[ ${#ports[@]} -eq 0 ]]; then
  echo "  none detected"
else
  for port in "${ports[@]}"; do
    printf '  %s\n' "$port"
  done
fi

echo
echo "Use a paired device ID with: ./dev adapters grant ADAPTER_ID DEVICE_ID --yes"
echo "Use a serial port with:       ./dev devices inspect /dev/ttyDEVICE"
