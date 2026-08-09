#!/bin/sh
set -eu

if [ "$#" -ne 2 ]; then
  echo "usage: $0 v1|v2 /dev/ttyDEVICE" >&2
  exit 2
fi
case "$1" in v1|v2) profile=$1 ;; *) echo "board profile must be v1 or v2" >&2; exit 2 ;; esac
port=$2
[ -e "$port" ] || { echo "serial device not found: $port" >&2; exit 1; }
repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
command -v idf.py >/dev/null 2>&1 || { echo "idf.py not found; activate ESP-IDF 6.0.2" >&2; exit 1; }
if [ "${INKMATE_HARDWARE_VERIFIED:-}" != "yes" ]; then
  echo "Refusing to flash an unverified profile." >&2
  echo "Verify PCB revision and memory, then set INKMATE_HARDWARE_VERIFIED=yes." >&2
  exit 1
fi
"$repo_dir/scripts/backup-flash.sh" "$profile" "$port"
INKMATE_BOARD_PROFILE=$profile idf.py -C "$repo_dir/firmware" -B "$repo_dir/firmware/build/$profile" -p "$port" flash
