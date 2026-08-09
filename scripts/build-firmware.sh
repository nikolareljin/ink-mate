#!/bin/sh
set -eu

if [ "$#" -ne 1 ]; then
  echo "usage: $0 v1|v2" >&2
  exit 2
fi
case "$1" in v1|v2) profile=$1 ;; *) echo "board profile must be v1 or v2" >&2; exit 2 ;; esac
repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
command -v idf.py >/dev/null 2>&1 || { echo "idf.py not found; activate ESP-IDF 6.0.2" >&2; exit 1; }
build_dir="$repo_dir/firmware/build/$profile"
# Keep profile output separate: a root firmware/sdkconfig from a prior profile
# must never override this explicit board configuration.
SDKCONFIG_DEFAULTS="sdkconfig.defaults;sdkconfig.$profile" \
    idf.py -C "$repo_dir/firmware" -B "$build_dir" \
    -D SDKCONFIG="$build_dir/sdkconfig" build
