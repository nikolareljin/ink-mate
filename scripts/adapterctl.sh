#!/usr/bin/env bash
# SCRIPT: adapterctl
# DESCRIPTION: Inspect and administer local application adapters
# USAGE: ./scripts/adapterctl.sh <status|list|approve|disable|grant|revoke|jobs|install-service> [OPTIONS]
# PARAMETERS:
#   status                         Check the local adapter host
#   list                           List registered adapters
#   approve ID FINGERPRINT --yes   Approve one discovered adapter
#   disable ID --yes               Disable an adapter
#   grant ID DEVICE --yes          Grant a device access to an adapter
#   revoke ID DEVICE --yes         Revoke a device grant
#   jobs                           List retained adapter jobs
#   install-service [--start] --yes Install a systemd user service
# ----------------------------------------------------
set -euo pipefail

repo_dir=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
if [[ ${1:-} == install-service ]]; then
  shift
  exec "$repo_dir/scripts/install-adapter-host-service.sh" "$@"
fi
env_file="$repo_dir/.env"
[[ -f "$env_file" ]] || { echo "missing .env; start the adapter host first" >&2; exit 1; }
url=$(sed -n 's/^INKMATE_ADAPTER_HOST_URL=//p' "$env_file" | tail -1)
token=$(sed -n 's/^INKMATE_ADAPTER_HOST_TOKEN=//p' "$env_file" | tail -1)
[[ -n "$url" && ${#token} -ge 32 ]] || { echo "adapter host is not configured; run ./dev run adapter-host" >&2; exit 1; }
auth=(-H "Authorization: Bearer $token")

command=${1:-status}
shift || true
need_yes() { [[ ${!#} = --yes ]] || { echo "$command requires --yes" >&2; exit 2; }; }
case "$command" in
  status) curl --silent --show-error --fail "$url/healthz" ;;
  list) curl --silent --show-error --fail "${auth[@]}" "$url/v1/adapters" ;;
  jobs) curl --silent --show-error --fail "${auth[@]}" "$url/v1/jobs" ;;
  approve)
    [[ $# -eq 3 ]] || { echo "usage: approve ID FINGERPRINT --yes" >&2; exit 2; }; need_yes
    curl --silent --show-error --fail -X POST "${auth[@]}" --data-urlencode "fingerprint=$2" "$url/v1/adapters/$1/approve" ;;
  disable)
    [[ $# -eq 2 ]] || { echo "usage: disable ID --yes" >&2; exit 2; }; need_yes
    curl --silent --show-error --fail -X POST "${auth[@]}" "$url/v1/adapters/$1/disable" ;;
  grant)
    [[ $# -eq 3 ]] || { echo "usage: grant ID DEVICE --yes" >&2; exit 2; }; need_yes
    curl --silent --show-error --fail -X POST "${auth[@]}" "$url/v1/adapters/$1/grants/$2" ;;
  revoke)
    [[ $# -eq 3 ]] || { echo "usage: revoke ID DEVICE --yes" >&2; exit 2; }; need_yes
    curl --silent --show-error --fail -X DELETE "${auth[@]}" "$url/v1/adapters/$1/grants/$2" ;;
  *) echo "unknown adapter command: $command" >&2; exit 2 ;;
esac
