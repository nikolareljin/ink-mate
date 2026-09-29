#!/bin/sh
# SCRIPT: configure-v2-enrollment
# DESCRIPTION: Write an enrolled V2 device identity into private firmware config
# USAGE: ./scripts/configure-v2-enrollment.sh [--replace] [DEVICE_ID]
# PARAMETERS:
#   --replace     Replace an existing private firmware configuration
#   DEVICE_ID     Select an enrolled device identity
# EXAMPLE: ./scripts/configure-v2-enrollment.sh inkmate-demo
# ----------------------------------------------------
set -eu

if [ "${1:-}" = -h ] || [ "${1:-}" = --help ]; then
  sed -n '/^# SCRIPT:/,/^# ----------------------------------------------------/s/^# \{0,1\}//p' "$0"
  exit 0
fi

if [ "$#" -gt 2 ]; then
  echo "usage: $0 [--replace] [DEVICE_ID]" >&2
  exit 2
fi

repo_dir=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
gateway_env="$repo_dir/.env"
private_sdkconfig="$repo_dir/firmware/sdkconfig.private"
if [ ! -f "$gateway_env" ]; then
  echo "missing $gateway_env; run scripts/enroll-v2-device.sh first" >&2
  exit 1
fi
wifi_ssid=$(sed -n 's/^INKMATE_WIFI_SSID=//p' "$gateway_env" | tail -1)
wifi_password=$(sed -n 's/^INKMATE_WIFI_PASSWORD=//p' "$gateway_env" | tail -1)
case "$wifi_ssid$wifi_password" in *\"*|*\\*) echo "Wi-Fi values contain unsupported characters" >&2; exit 2 ;; esac
replace=false
if [ "${1:-}" = --replace ]; then replace=true; fi
if [ -e "$private_sdkconfig" ] && [ "$replace" != true ]; then
  echo "refusing to overwrite $private_sdkconfig" >&2
  exit 1
fi

entries=$(sed -n 's/^INKMATE_DEVICE_SECRETS=//p' "$gateway_env")
if [ -z "$entries" ]; then
  echo "missing INKMATE_DEVICE_SECRETS in $gateway_env" >&2
  exit 1
fi
requested=${1:-}
if [ "$replace" = true ]; then requested=${2:-}; fi
match=''
old_ifs=$IFS
IFS=,
for entry in $entries; do
  device_id=${entry%%:*}
  secret=${entry#*:}
  case "$device_id" in
    *[!a-z0-9_-]* | '') continue ;;
  esac
  if [ "${#device_id}" -gt 32 ] || [ "$device_id" = "$entry" ] || [ "${#secret}" -lt 32 ]; then
    continue
  fi
  case "$secret" in
    *\"* | *\\*) continue ;;
  esac
  if [ -z "$secret" ]; then
    continue
  fi
  if [ -n "$requested" ] && [ "$device_id" != "$requested" ]; then
    continue
  fi
  if [ -n "$match" ]; then
    IFS=$old_ifs
    echo "multiple matching device enrollments; provide DEVICE_ID" >&2
    exit 2
  fi
  match=$entry
done
IFS=$old_ifs
if [ -z "$match" ]; then
  echo "no matching device enrollment" >&2
  exit 1
fi
device_id=${match%%:*}
secret=${match#*:}
old_umask=$(umask)
umask 077
trap 'umask "$old_umask"' EXIT HUP INT TERM
{
  printf 'CONFIG_INKMATE_GATEWAY_DEVICE_ID="%s"\n' "$device_id"
  printf 'CONFIG_INKMATE_GATEWAY_DEVICE_SECRET="%s"\n' "$secret"
  printf 'CONFIG_INKMATE_WIFI_SSID="%s"\n' "$wifi_ssid"
  printf 'CONFIG_INKMATE_WIFI_PASSWORD="%s"\n' "$wifi_password"
} >"$private_sdkconfig"
printf '%s\n' "configured firmware enrollment for $device_id"
