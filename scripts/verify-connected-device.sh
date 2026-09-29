#!/usr/bin/env bash
# SCRIPT: verify-connected-device
# DESCRIPTION: Inspect hardware, verify flash bytes, and capture a boot log
# USAGE: ./scripts/verify-connected-device.sh v1|v2 /dev/ttyDEVICE
# PARAMETERS:
#   PROFILE    Required board profile, v1 or v2
#   DEVICE     Required serial device path
# EXAMPLE: ./scripts/verify-connected-device.sh v2 /dev/ttyACM0
# ----------------------------------------------------
set -euo pipefail

if [[ ${1:-} == -h || ${1:-} == --help ]]; then
  sed -n '/^# SCRIPT:/,/^# ----------------------------------------------------/s/^# \{0,1\}//p' "$0"
  exit 0
fi

if [ "$#" -ne 2 ]; then
  echo "usage: $0 v1|v2 /dev/ttyDEVICE" >&2
  exit 2
fi

case "$1" in
  v1|v2) profile=$1 ;;
  *) echo "board profile must be v1 or v2" >&2; exit 2 ;;
esac
port=$2
repo_dir=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
idf_dir=${INKMATE_ESP_IDF_DIR:-"$repo_dir/.tools/esp-idf"}
if [[ -f "$idf_dir/export.sh" ]]; then
  # shellcheck source=/dev/null
  source "$idf_dir/export.sh" >/dev/null
fi

"$repo_dir/scripts/inspect-hardware.sh" "$port"
"$repo_dir/scripts/verify-flash.sh" "$profile" "$port"
"$repo_dir/scripts/capture-boot-log.sh" "$port"
