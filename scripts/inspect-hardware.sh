#!/bin/sh
set -eu

if [ "$#" -ne 1 ]; then
  echo "usage: $0 /dev/ttyDEVICE" >&2
  exit 2
fi
port=$1
[ -e "$port" ] || { echo "serial device not found: $port" >&2; exit 1; }
command -v esptool.py >/dev/null 2>&1 || { echo "esptool.py not found" >&2; exit 1; }

echo "InkMate hardware inspection (MAC address intentionally omitted)"
esptool.py --port "$port" chip_id
esptool.py --port "$port" flash_id
echo "PSRAM size is confirmed by the ESP-IDF boot log, not flash_id."
