#!/usr/bin/env bash
# SCRIPT: dev
# DESCRIPTION: Run InkMate development and local adapter commands
# USAGE: ./dev <install|build|run|test|status|devices|preflight|adapters|jobs|previews> [OPTIONS]
# PARAMETERS:
#   run gateway|adapter-host     Start a foreground service
#   adapters COMMAND             Run adapter administration or install-service
#   jobs                         List retained adapter jobs
#   previews                     Render black-and-white V2 state PNGs
# ----------------------------------------------------
set -euo pipefail

repo_dir=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
verb=${1:-}
shift || true
case "$verb" in
  install|build|test|deploy|update) exec "$repo_dir/$verb" "$@" ;;
  run)
    case ${1:-} in
      gateway) shift; exec "$repo_dir/scripts/start-device-gateway.sh" "$@" ;;
      adapter-host) shift; exec "$repo_dir/scripts/start-adapter-host.sh" "$@" ;;
      *) echo "run requires gateway or adapter-host" >&2; exit 2 ;;
    esac ;;
  status) exec "$repo_dir/scripts/adapterctl.sh" status "$@" ;;
  devices) exec "$repo_dir/scripts/inspect-connected-device.sh" "$@" ;;
  preflight) exec "$repo_dir/scripts/check.sh" "$@" ;;
  adapters) exec "$repo_dir/scripts/adapterctl.sh" "$@" ;;
  jobs) exec "$repo_dir/scripts/adapterctl.sh" jobs "$@" ;;
  previews) exec "$repo_dir/scripts/render-display-previews.py" "$@" ;;
  ''|-h|--help) sed -n '/^# SCRIPT:/,/^# ----------------------------------------------------/s/^# \{0,1\}//p' "$0" ;;
  *) echo "unknown command: $verb" >&2; exec "$0" --help ;;
esac
