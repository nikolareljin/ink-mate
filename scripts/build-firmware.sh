#!/bin/sh
set -eu

if [ "$#" -ne 1 ]; then
  echo "usage: $0 v1|v2" >&2
  exit 2
fi
case "$1" in v1|v2) profile=$1 ;; *) echo "board profile must be v1 or v2" >&2; exit 2 ;; esac
repo_dir=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
command -v idf.py >/dev/null 2>&1 || { echo "idf.py not found; activate ESP-IDF 6.0.2" >&2; exit 1; }
private_sdkconfig=${INKMATE_PRIVATE_SDKCONFIG:-"$repo_dir/firmware/sdkconfig.private"}
sdkconfig_defaults="sdkconfig.defaults;sdkconfig.$profile"
if [ -n "${INKMATE_PRIVATE_SDKCONFIG:-}" ] && [ ! -f "$private_sdkconfig" ]; then
  echo "INKMATE_PRIVATE_SDKCONFIG does not exist: $private_sdkconfig" >&2
  exit 2
fi
if [ -f "$private_sdkconfig" ]; then
  sdkconfig_defaults="$sdkconfig_defaults;$private_sdkconfig"
fi
build_name=$profile
if [ "$profile" = v2 ] && [ -f "$private_sdkconfig" ]; then
  build_name="$profile-private"
fi
build_dir="$repo_dir/firmware/build/$build_name"
# Keep profile output separate: a root firmware/sdkconfig from a prior profile
# must never override this explicit board configuration.
SDKCONFIG_DEFAULTS="$sdkconfig_defaults" \
    idf.py -C "$repo_dir/firmware" -B "$build_dir" \
    -D SDKCONFIG="$build_dir/sdkconfig" build
