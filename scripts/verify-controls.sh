#!/bin/sh
set -eu

if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
  echo "usage: $0 /dev/ttyDEVICE [seconds]" >&2
  exit 2
fi

port=$1
duration=${2:-30}
[ -e "$port" ] || { echo "serial device not found: $port" >&2; exit 1; }
case "$duration" in
  *[!0-9]*|'') echo "seconds must be a positive integer" >&2; exit 2 ;;
esac
[ "$duration" -gt 0 ] || { echo "seconds must be greater than zero" >&2; exit 2; }
command -v python3 >/dev/null 2>&1 || { echo "python3 not found" >&2; exit 1; }
python3 -c 'import serial' >/dev/null 2>&1 || {
  echo "pyserial is not installed; install the gateway dependencies or pyserial" >&2
  exit 1
}

repo_dir=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
report_dir="$repo_dir/hardware-reports"
stamp=$(date -u +%Y%m%dT%H%M%SZ)
report="$report_dir/controls-$stamp.log"
umask 077
mkdir -p "$report_dir"

echo "Press BOOT briefly, then hold BOOT for at least 700 ms and release."
echo "Holding PWR for 2 seconds releases the battery latch and may power down the board."

python3 - "$port" "$duration" "$report" <<'PY'
import re
import sys
import time

import serial

port = sys.argv[1]
duration = int(sys.argv[2])
report = sys.argv[3]
allowed = re.compile(r"\b(inkmate\.controls|inkmate\.epaper|error|fatal|panic|assert|abort)\b", re.IGNORECASE)
blocked = re.compile(r"password|token|secret|credential|\bmac\b|\bssid\b", re.IGNORECASE)

with serial.Serial(port, 115200, timeout=0.2, rtscts=False, dsrdtr=False) as connection:
    deadline = time.monotonic() + duration
    chunks = []
    while time.monotonic() < deadline:
        chunk = connection.read(connection.in_waiting or 1)
        if chunk:
            chunks.append(chunk)

lines = b"".join(chunks).decode("utf-8", errors="replace").splitlines()
safe_lines = [line for line in lines if allowed.search(line) and not blocked.search(line)]
with open(report, "w", encoding="utf-8") as output:
    output.write("\n".join(safe_lines))
    if safe_lines:
        output.write("\n")
print(f"Saved {len(safe_lines)} filtered control diagnostics to {report}")
PY
