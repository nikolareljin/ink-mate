#!/bin/sh
set -eu

repo_dir=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
gateway_env="$repo_dir/.env"
if [ ! -f "$gateway_env" ]; then
  echo "missing $gateway_env; run scripts/enroll-v2-device.sh first" >&2
  exit 1
fi

gateway_interface=$(sed -n 's/^INKMATE_GATEWAY_INTERFACE=//p' "$gateway_env" | tail -1)
if [ -z "$gateway_interface" ]; then
  echo "INKMATE_GATEWAY_INTERFACE is required for device discovery." >&2
  echo "Set it in $gateway_env to the Wi-Fi interface on the device LAN." >&2
  ip -o -4 addr show scope global | awk '{split($4, address, "/"); print "available: " $2 " " address[1]}' >&2
  exit 2
fi

gateway_cidr=$(ip -o -4 addr show dev "$gateway_interface" scope global 2>/dev/null | awk 'NR == 1 {print $4}')
if [ -z "$gateway_cidr" ]; then
  echo "INKMATE_GATEWAY_INTERFACE has no IPv4 address: $gateway_interface" >&2
  exit 2
fi
gateway_address=${gateway_cidr%/*}

if grep -q '^INKMATE_BIND_ADDRESS=' "$gateway_env"; then
  sed -i "s|^INKMATE_BIND_ADDRESS=.*|INKMATE_BIND_ADDRESS=$gateway_address|" "$gateway_env"
else
  printf '\nINKMATE_BIND_ADDRESS=%s\n' "$gateway_address" >>"$gateway_env"
fi

if grep -q '^INKMATE_GATEWAY_NETWORK=' "$gateway_env"; then
  sed -i "s|^INKMATE_GATEWAY_NETWORK=.*|INKMATE_GATEWAY_NETWORK=$gateway_cidr|" "$gateway_env"
else
  printf 'INKMATE_GATEWAY_NETWORK=%s\n' "$gateway_cidr" >>"$gateway_env"
fi

configured_port=$(sed -n 's/^INKMATE_GATEWAY_PORT=//p' "$gateway_env" | tail -1)
case "$configured_port" in
  '') ;;
  *[!0-9]*)
    echo "INKMATE_GATEWAY_PORT must be numeric" >&2
    exit 2
    ;;
  *)
    if [ "$configured_port" -lt 1024 ] || [ "$configured_port" -gt 65535 ]; then
      echo "INKMATE_GATEWAY_PORT must be between 1024 and 65535" >&2
      exit 2
    fi
    ;;
esac
if [ -z "$configured_port" ]; then
  configured_port=8080
  if ss -ltn "sport = :$configured_port" | grep -q LISTEN; then
    configured_port=8765
    while ss -ltn "sport = :$configured_port" | grep -q LISTEN; do
      configured_port=$((configured_port + 1))
    done
  fi
  printf '\nINKMATE_GATEWAY_PORT=%s\n' "$configured_port" >>"$gateway_env"
fi

exec docker compose -f "$repo_dir/compose.device.yaml" up --detach --build
