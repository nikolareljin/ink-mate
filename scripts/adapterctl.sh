#!/usr/bin/env bash
# SCRIPT: adapterctl
# DESCRIPTION: Inspect and administer local application adapters
# USAGE: ./scripts/adapterctl.sh <status|list|approve|disable|grant|revoke|jobs|install-service> [OPTIONS]
# PARAMETERS:
#   status                         Check the local adapter host
#   list                           List adapters with full SHA-256 fingerprints
#   approve ID FINGERPRINT [--yes] Approve one adapter and print the next grant command
#   disable ID --yes               Disable an adapter
#   grant ID DEVICE --yes          Grant a device access to an adapter
#   revoke ID DEVICE --yes         Revoke a device grant
#   jobs                           List retained adapter jobs
#   install-service [--start] --yes Install a systemd user service
# EXAMPLE:
#   ./dev adapters list
#   # Copy the SHA-256 line printed by `adapters list`.
#   ./dev adapters approve nikos-vscode 0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
#   # Result: Approved adapter: nikos-vscode
#   # Next:   ./dev adapters grant nikos-vscode DEVICE_ID --yes
#   ./dev adapters grant nikos-vscode inkmate-demo --yes
# ----------------------------------------------------
set -euo pipefail

if [[ ${1:-} == -h || ${1:-} == --help ]]; then
  sed -n '/^# SCRIPT:/,/^# ----------------------------------------------------/s/^# \{0,1\}//p' "$0"
  exit 0
fi

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
format_adapters() {
  jq -r '
    if type != "array" then error("adapter host returned an invalid list")
    elif length == 0 then "No adapters are registered."
    else .[] |
      "Adapter ID:  \(.adapter_id)\n" +
      "State:       \(.state)\n" +
      "SHA-256:     \(.fingerprint)\n" +
      "Transport:   \(.manifest.transport)\n" +
      "Operations:  \([.manifest.operations[].operation_id] | join(", "))\n"
    end
  '
}
need_yes() { [[ ${!#} = --yes ]] || { echo "$command requires --yes" >&2; exit 2; }; }
confirm() {
  local prompt=$1
  local assume_yes=${2:-}
  if [[ $assume_yes = --yes ]]; then return; fi
  [[ -t 0 ]] || { echo "$command requires --yes without a terminal" >&2; exit 2; }
  read -r -p "$prompt [y/N] " answer
  [[ $answer =~ ^[Yy]([Ee][Ss])?$ ]] || { echo "cancelled" >&2; exit 1; }
}
case "$command" in
  status) curl --silent --show-error --fail "$url/healthz" ;;
  list)
    command -v jq >/dev/null 2>&1 || { echo "jq is required to format adapter fingerprints" >&2; exit 1; }
    curl --silent --show-error --fail "${auth[@]}" "$url/v1/adapters" | format_adapters ;;
  jobs) curl --silent --show-error --fail "${auth[@]}" "$url/v1/jobs" ;;
  approve)
    [[ $# -eq 2 || $# -eq 3 ]] || { echo "usage: approve ID FINGERPRINT [--yes]" >&2; exit 2; }; confirm "Approve adapter '$1'?" "${3:-}"
    curl --silent --show-error --fail -X POST --get "${auth[@]}" --data-urlencode "fingerprint=$2" "$url/v1/adapters/$1/approve" >/dev/null
    printf 'Approved adapter: %s\n' "$1"
    printf 'Next: ./dev adapters grant %s DEVICE_ID --yes\n' "$1" ;;
  disable)
    [[ $# -eq 2 ]] || { echo "usage: disable ID --yes" >&2; exit 2; }; need_yes "$@"
    curl --silent --show-error --fail -X POST "${auth[@]}" "$url/v1/adapters/$1/disable" ;;
  grant)
    [[ $# -eq 3 ]] || { echo "usage: grant ID DEVICE --yes" >&2; exit 2; }; need_yes "$@"
    curl --silent --show-error --fail -X POST "${auth[@]}" "$url/v1/adapters/$1/grants/$2" ;;
  revoke)
    [[ $# -eq 3 ]] || { echo "usage: revoke ID DEVICE --yes" >&2; exit 2; }; need_yes "$@"
    curl --silent --show-error --fail -X DELETE "${auth[@]}" "$url/v1/adapters/$1/grants/$2" ;;
  *) echo "unknown adapter command: $command" >&2; exit 2 ;;
esac
