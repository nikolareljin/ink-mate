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
report="$report_dir/audio-capture-$stamp.log"
umask 077
mkdir -p "$report_dir"

echo "Press and keep holding BOOT. Start speaking while still holding it, then release BOOT when done."
echo "The capture is limited to 10 seconds and is discarded after local WAV validation."

python3 - "$port" "$duration" "$report" <<'PY'
import re
import sys
import time

import serial

port = sys.argv[1]
duration = int(sys.argv[2])
report = sys.argv[3]
allowed = re.compile(
    r"\b(inkmate\.(?:audio|controls|discovery|gateway|epaper)|es8311|audio_codec|i2c_if|i2s_if|"
    r"error|fatal|panic|assert|abort)\b",
    re.IGNORECASE,
)
blocked = re.compile(r"password|token|secret|credential|\bmac\b|\bssid\b", re.IGNORECASE)

safe_lines = []
with open(report, "w", encoding="utf-8") as output:
    with serial.Serial(port, 115200, timeout=0.2, rtscts=False, dsrdtr=False) as connection:
        deadline = time.monotonic() + duration
        partial = b""
        while time.monotonic() < deadline:
            chunk = connection.read(connection.in_waiting or 1)
            if not chunk:
                continue
            partial += chunk
            complete, separator, partial = partial.rpartition(b"\n")
            if not separator:
                continue
            for line in complete.decode("utf-8", errors="replace").splitlines():
                if allowed.search(line) and not blocked.search(line):
                    print(line, flush=True)
                    output.write(line + "\n")
                    output.flush()
                    safe_lines.append(line)

        if partial:
            line = partial.decode("utf-8", errors="replace")
            if allowed.search(line) and not blocked.search(line):
                print(line, flush=True)
                output.write(line + "\n")
                safe_lines.append(line)
print(f"Saved {len(safe_lines)} filtered audio diagnostics to {report}")
PY
