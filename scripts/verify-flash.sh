#!/bin/sh
set -eu

if [ "$#" -ne 2 ]; then
  echo "usage: $0 v1|v2 /dev/ttyDEVICE" >&2
  exit 2
fi

case "$1" in
  v1|v2) profile=$1 ;;
  *) echo "board profile must be v1 or v2" >&2; exit 2 ;;
esac

port=$2
[ -e "$port" ] || { echo "serial device not found: $port" >&2; exit 1; }
command -v python >/dev/null 2>&1 || { echo "python not found" >&2; exit 1; }

repo_dir=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
build_dir="$repo_dir/firmware/build/$profile"
manifest="$build_dir/flasher_args.json"
[ -f "$manifest" ] || {
  echo "flash manifest not found: build the $profile firmware first" >&2
  exit 1
}

python - "$manifest" "$build_dir" "$port" <<'PY'
import json
import subprocess
import sys
from pathlib import Path

manifest_path = Path(sys.argv[1])
build_dir = Path(sys.argv[2]).resolve()
port = sys.argv[3]
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

required_entries = ("bootloader", "partition-table", "app")
arguments = [
    sys.executable,
    "-m",
    "esptool",
    "--chip",
    "esp32s3",
    "--port",
    port,
    "--after",
    "hard-reset",
    "verify-flash",
]

for name in required_entries:
    entry = manifest.get(name)
    if not isinstance(entry, dict) or not entry.get("offset") or not entry.get("file"):
        raise SystemExit(f"missing {name} entry in {manifest_path}")
    image = (build_dir / entry["file"]).resolve()
    if build_dir not in image.parents or not image.is_file():
        raise SystemExit(f"flash image not found under build directory: {entry['file']}")
    arguments.extend((entry["offset"], str(image)))

result = subprocess.run(arguments, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
for line in result.stdout.splitlines():
    if "MAC:" not in line:
        print(line)
if result.returncode:
    raise SystemExit(result.returncode)

print("Verified bootloader, partition table, and application image.")
print("OTA metadata is excluded: the bootloader updates it when selecting the active slot.")
PY
