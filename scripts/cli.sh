#!/usr/bin/env bash
# SCRIPT: dev
# DESCRIPTION: Run InkMate development and local adapter commands
# USAGE: ./dev COMMAND [OPTIONS]
# PARAMETERS:
#   install                       Install project dependencies
#   build                         Build firmware, gateway image, and docs
#   test                          Run project tests
#   deploy [OPTIONS]              Deploy firmware to a verified device
#   update [OPTIONS]              Update pinned project dependencies
#   run gateway                   Build and start the device-facing gateway
#   run adapter-host              Start the loopback-only adapter host in this terminal
#   stop                          Stop the gateway container
#   status                        Check adapter host health
#   devices [OPTIONS]             Inspect a connected InkMate device
#   preflight                     Run the repository check suite
#   previews                      Render V2 display preview images
#   jobs                          List retained adapter jobs
#   adapters install-service [--start] --yes
#                                 Install the adapter host systemd user service
#   adapters status               Check adapter host health
#   adapters list                 Print adapter IDs, states, operations, and SHA-256 fingerprints
#   adapters approve ID FINGERPRINT [--yes]
#                                 Copy FINGERPRINT from `adapters list`; do not use an adapter alias
#   adapters grant ID DEVICE_ID --yes
#                                 Grant one paired device access to an approved adapter
#   adapters revoke ID DEVICE_ID --yes
#                                 Remove one device grant
#   adapters disable ID --yes     Disable an adapter for every device
#   adapters jobs                 List retained accepted adapter jobs
# EXAMPLE:
#   ./dev run adapter-host
#   ./dev adapters list
#   # Example output: SHA-256: 0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
#   ./dev adapters approve nikos-vscode 0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
#   ./dev adapters grant nikos-vscode inkmate-demo --yes
#   ./dev adapters list
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
  stop) exec "$repo_dir/scripts/stop-device-gateway.sh" "$@" ;;
  status) exec "$repo_dir/scripts/adapterctl.sh" status "$@" ;;
  devices) exec "$repo_dir/scripts/inspect-connected-device.sh" "$@" ;;
  preflight) exec "$repo_dir/scripts/check.sh" "$@" ;;
  adapters) exec "$repo_dir/scripts/adapterctl.sh" "$@" ;;
  jobs) exec "$repo_dir/scripts/adapterctl.sh" jobs "$@" ;;
  previews) exec "$repo_dir/scripts/render-display-previews.py" "$@" ;;
  ''|-h|--help) sed -n '/^# SCRIPT:/,/^# ----------------------------------------------------/s/^# \{0,1\}//p' "$0" ;;
  *) echo "unknown command: $verb" >&2; exec "$0" --help ;;
esac
