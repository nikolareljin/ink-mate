#!/usr/bin/env bash
# SCRIPT: inspect-connected-device
# DESCRIPTION: Install ESP-IDF if needed and inspect one connected device
# USAGE: ./scripts/inspect-connected-device.sh /dev/ttyDEVICE
# PARAMETERS:
#   DEVICE    Required serial device path
# EXAMPLE: ./dev devices /dev/ttyACM0
# ----------------------------------------------------
set -euo pipefail

if [[ ${1:-} == -h || ${1:-} == --help ]]; then
  sed -n '/^# SCRIPT:/,/^# ----------------------------------------------------/s/^# \{0,1\}//p' "$0"
  exit 0
fi

if [[ "$#" -ne 1 ]]; then
  echo "usage: $0 /dev/ttyDEVICE" >&2
  exit 2
fi

repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
idf_dir=${INKMATE_ESP_IDF_DIR:-"$repo_dir/.tools/esp-idf"}

if [[ ! -f "$idf_dir/export.sh" ]]; then
  "$repo_dir/scripts/install-esp-idf.sh" "$idf_dir"
fi

# ESP-IDF sets PATH and Python environment variables required by esptool.py.
# shellcheck disable=SC1090
source "$idf_dir/export.sh"
exec "$repo_dir/scripts/inspect-hardware.sh" "$1"
