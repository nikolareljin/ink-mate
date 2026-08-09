#!/bin/sh
set -eu

if [ "$#" -ne 2 ]; then
  echo "usage: $0 v1|v2 /dev/ttyDEVICE" >&2
  exit 2
fi
case "$1" in
  v1) flash_size=0x400000 ;;
  v2) flash_size=0x800000 ;;
  *) echo "board profile must be v1 or v2" >&2; exit 2 ;;
esac
port=$2
[ -e "$port" ] || { echo "serial device not found: $port" >&2; exit 1; }
repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
backup_dir=${INKMATE_FLASH_BACKUP_DIR:-"$repo_dir/firmware/backups"}
stamp=$(date -u +%Y%m%dT%H%M%SZ)
umask 077
mkdir -p "$backup_dir"
backup_file="$backup_dir/flash-$1-$stamp.bin"

python -m esptool --chip esp32s3 --no-stub -b 115200 -p "$port" \
  read-flash 0x0 "$flash_size" "$backup_file"
sha256sum "$backup_file" >"$backup_file.sha256"
printf '%s\n' "$backup_file"
