#!/bin/sh
# SCRIPT: inspect-hardware
# DESCRIPTION: Report connected ESP32-S3 flash and chip details without MAC output
# USAGE: ./scripts/inspect-hardware.sh /dev/ttyDEVICE
# PARAMETERS:
#   DEVICE    Required serial device path
# EXAMPLE: ./scripts/inspect-hardware.sh /dev/ttyACM0
# ----------------------------------------------------
set -eu

if [ "${1:-}" = -h ] || [ "${1:-}" = --help ]; then
  sed -n '/^# SCRIPT:/,/^# ----------------------------------------------------/s/^# \{0,1\}//p' "$0"
  exit 0
fi

if [ "$#" -ne 1 ]; then
  echo "usage: $0 /dev/ttyDEVICE" >&2
  exit 2
fi
port=$1
[ -e "$port" ] || { echo "serial device not found: $port" >&2; exit 1; }
command -v python >/dev/null 2>&1 || { echo "python not found" >&2; exit 1; }
python -m esptool version >/dev/null 2>&1 || {
  echo "esptool is not available; activate ESP-IDF or run verify-connected-device.sh" >&2
  exit 1
}

echo "InkMate hardware inspection (MAC address intentionally omitted)"
run_esptool() {
  output_file=$(mktemp)
  if python -m esptool --port "$port" "$@" >"$output_file" 2>&1; then
    status=0
  else
    status=$?
  fi
  sed '/MAC:/d' "$output_file"
  rm -f "$output_file"
  return "$status"
}

run_esptool chip-id
run_esptool flash-id
echo "PSRAM size is confirmed by the ESP-IDF boot log, not flash-id."
