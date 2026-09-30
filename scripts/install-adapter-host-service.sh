#!/usr/bin/env bash
# SCRIPT: install-adapter-host-service
# DESCRIPTION: Install the local adapter host as a user service
# USAGE: ./scripts/install-adapter-host-service.sh [--start] --yes
# PARAMETERS:
#   --start    Enable and start the user service after installation
#   --yes      Confirm writing the user service definition
# EXAMPLE: ./dev adapters install-service --start --yes
# ----------------------------------------------------
set -euo pipefail

if [[ ${1:-} == -h || ${1:-} == --help ]]; then
  sed -n '/^# SCRIPT:/,/^# ----------------------------------------------------/s/^# \{0,1\}//p' "$0"
  exit 0
fi

repo_dir=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
start=false
for argument in "$@"; do
  case "$argument" in
    --start) start=true ;;
    --yes) ;;
    *) echo "usage: $0 [--start] --yes" >&2; exit 2 ;;
  esac
done
[[ " $* " == *" --yes "* ]] || { echo "service installation requires --yes" >&2; exit 2; }

unit_dir="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
unit_file="$unit_dir/inkmate-adapter-host.service"
mkdir -p "$unit_dir"
umask 077
printf '%s\n' \
  '[Unit]' \
  'Description=InkMate local adapter host' \
  'After=network-online.target' \
  '' \
  '[Service]' \
  'Type=simple' \
  "WorkingDirectory=$repo_dir" \
  "ExecStart=$repo_dir/scripts/start-adapter-host.sh" \
  'Restart=on-failure' \
  'RestartSec=3' \
  '' \
  '[Install]' \
  'WantedBy=default.target' > "$unit_file"
systemctl --user daemon-reload
if "$start"; then
  systemctl --user enable --now inkmate-adapter-host.service
fi
echo "installed $unit_file"
