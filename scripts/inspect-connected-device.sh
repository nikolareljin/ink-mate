#!/usr/bin/env bash
set -euo pipefail

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
