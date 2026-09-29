#!/bin/sh
# SCRIPT: stop-device-gateway
# DESCRIPTION: Stop the InkMate gateway container without removing its data
# USAGE: ./scripts/stop-device-gateway.sh
# ----------------------------------------------------
set -eu

repo_dir=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)

if [ "$#" -ne 0 ]; then
  echo "usage: $0" >&2
  exit 2
fi

exec docker compose -f "$repo_dir/compose.device.yaml" stop
