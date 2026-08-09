#!/usr/bin/env bash
set -euo pipefail

if [[ "$#" -gt 1 ]]; then
  echo "usage: $0 [ESP_IDF_DIRECTORY]" >&2
  exit 2
fi

repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
idf_dir=${1:-"$repo_dir/.tools/esp-idf"}
idf_version=v6.0.2

command -v git >/dev/null 2>&1 || {
  echo "git is required to install ESP-IDF" >&2
  exit 1
}
command -v python3 >/dev/null 2>&1 || {
  echo "python3 is required to install ESP-IDF" >&2
  exit 1
}

if [[ -e "$idf_dir" && ! -f "$idf_dir/export.sh" ]]; then
  echo "ESP-IDF directory exists but does not contain export.sh: $idf_dir" >&2
  exit 1
fi

if [[ ! -d "$idf_dir" ]]; then
  echo "Cloning ESP-IDF $idf_version into $idf_dir"
  mkdir -p -- "$(dirname -- "$idf_dir")"
  git clone --branch "$idf_version" --depth 1 --recursive \
    https://github.com/espressif/esp-idf.git "$idf_dir"
fi

echo "Installing ESP32-S3 tools and Python dependencies"
"$idf_dir/install.sh" esp32s3

echo "ESP-IDF is ready. Activate it with: . $idf_dir/export.sh"
