#!/usr/bin/env bash
# SCRIPT: start-adapter-host
# DESCRIPTION: Start the local-only application adapter host
# USAGE: ./scripts/start-adapter-host.sh
# PARAMETERS:
#   None
# EXAMPLE: ./dev run adapter-host
# ----------------------------------------------------
set -euo pipefail

if [[ ${1:-} == -h || ${1:-} == --help ]]; then
  sed -n '/^# SCRIPT:/,/^# ----------------------------------------------------/s/^# \{0,1\}//p' "$0"
  exit 0
fi

repo_dir=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
env_file="$repo_dir/.env"
python_bin="$repo_dir/gateway/.venv/bin/python"

[[ -x "$python_bin" ]] || { echo "gateway dependencies are missing; run ./install --skip-esp-idf --skip-docs" >&2; exit 1; }
[[ -f "$env_file" ]] || cp "$repo_dir/.env.example" "$env_file"
chmod 600 "$env_file"

set_value() {
  local key=$1 value=$2
  if grep -q "^${key}=" "$env_file"; then
    sed -i "s|^${key}=.*|${key}=${value}|" "$env_file"
  else
    printf '\n%s=%s\n' "$key" "$value" >>"$env_file"
  fi
}

token=$(sed -n 's/^INKMATE_ADAPTER_HOST_TOKEN=//p' "$env_file" | tail -1)
if [[ ${#token} -lt 32 ]]; then
  token=$(openssl rand -hex 32)
  set_value INKMATE_ADAPTER_HOST_TOKEN "$token"
fi
port=$(sed -n 's/^INKMATE_ADAPTER_HOST_PORT=//p' "$env_file" | tail -1)
port=${port:-8764}
set_value INKMATE_ADAPTER_HOST_PORT "$port"
set_value INKMATE_ADAPTER_HOST_URL "http://127.0.0.1:${port}"
state_dir=$(sed -n 's/^INKMATE_ADAPTER_STATE_DIR=//p' "$env_file" | tail -1)
state_dir=${state_dir:-"$HOME/.local/state/inkmate/adapters"}
set_value INKMATE_ADAPTER_STATE_DIR "$state_dir"

exec env \
  "INKMATE_ADAPTER_HOST_TOKEN=$token" \
  "INKMATE_ADAPTER_STATE_DIR=$state_dir" \
  "INKMATE_ADAPTER_HOST_PORT=$port" \
  "$python_bin" -m inkmate_gateway.adapter_host
