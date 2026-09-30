#!/bin/sh
# SCRIPT: stop-device-gateway
# DESCRIPTION: Stop the InkMate gateway container without removing its data
# USAGE: ./scripts/stop-device-gateway.sh
# PARAMETERS:
#   None
# EXAMPLE: ./dev stop
# ----------------------------------------------------
set -eu

if [ "${1:-}" = -h ] || [ "${1:-}" = --help ]; then
  sed -n '/^# SCRIPT:/,/^# ----------------------------------------------------/s/^# \{0,1\}//p' "$0"
  exit 0
fi

repo_dir=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)

if [ "$#" -ne 0 ]; then
  echo "usage: $0" >&2
  exit 2
fi

exec docker compose -f "$repo_dir/compose.device.yaml" stop
