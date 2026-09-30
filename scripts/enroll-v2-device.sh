#!/bin/sh
# SCRIPT: enroll-v2-device
# DESCRIPTION: Create a new device identity and pairing secret
# USAGE: ./scripts/enroll-v2-device.sh DEVICE_ID
# PARAMETERS:
#   DEVICE_ID    Lowercase letters, digits, hyphens, and underscores only
# EXAMPLE: ./scripts/enroll-v2-device.sh inkmate-demo
# ----------------------------------------------------
set -eu

if [ "${1:-}" = -h ] || [ "${1:-}" = --help ]; then
  sed -n '/^# SCRIPT:/,/^# ----------------------------------------------------/s/^# \{0,1\}//p' "$0"
  exit 0
fi

if [ "$#" -ne 1 ]; then
  echo "usage: $0 DEVICE_ID" >&2
  exit 2
fi

device_id=$1
case "$device_id" in
  *[!a-z0-9_-]* | '')
    echo "DEVICE_ID must contain lowercase letters, digits, hyphens, or underscores" >&2
    exit 2
    ;;
esac
if [ "${#device_id}" -gt 32 ]; then
  echo "DEVICE_ID must be at most 32 characters" >&2
  exit 2
fi

repo_dir=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
private_sdkconfig="$repo_dir/firmware/sdkconfig.private"
gateway_env="$repo_dir/.env"
if [ -e "$private_sdkconfig" ]; then
  echo "refusing to overwrite $private_sdkconfig" >&2
  exit 1
fi
if [ -e "$gateway_env" ] && grep -q '^INKMATE_DEVICE_SECRETS=' "$gateway_env"; then
  echo "refusing to replace INKMATE_DEVICE_SECRETS in $gateway_env" >&2
  exit 1
fi
command -v openssl >/dev/null 2>&1 || { echo "openssl is required" >&2; exit 1; }
secret=$(openssl rand -hex 32)
old_umask=$(umask)
umask 077
trap 'umask "$old_umask"' EXIT HUP INT TERM
{
  printf 'CONFIG_INKMATE_GATEWAY_DEVICE_ID="%s"\n' "$device_id"
  printf 'CONFIG_INKMATE_GATEWAY_DEVICE_SECRET="%s"\n' "$secret"
} >"$private_sdkconfig"
if [ -e "$gateway_env" ]; then
  printf '\nINKMATE_DEVICE_SECRETS=%s:%s\n' "$device_id" "$secret" >>"$gateway_env"
else
  printf 'INKMATE_DEVICE_SECRETS=%s:%s\n' "$device_id" "$secret" >"$gateway_env"
fi
printf '%s\n' "enrolled $device_id; build with ./scripts/build-firmware.sh v2 and start the LAN gateway with docker compose -f compose.device.yaml up --build"
