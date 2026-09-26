#!/bin/sh
set -eu

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
