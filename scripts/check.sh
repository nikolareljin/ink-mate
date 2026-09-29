#!/usr/bin/env bash
# SCRIPT: check
# DESCRIPTION: Run all available local InkMate validation checks
# USAGE: ./scripts/check.sh
# PARAMETERS:
#   None
# EXAMPLE: ./dev preflight
# ----------------------------------------------------
set -euo pipefail

if [[ ${1:-} == -h || ${1:-} == --help ]]; then
  sed -n '/^# SCRIPT:/,/^# ----------------------------------------------------/s/^# \{0,1\}//p' "$0"
  exit 0
fi

repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$repo_dir"

helpers="$repo_dir/scripts/script-helpers/helpers.sh"
if [[ ! -f "$helpers" ]]; then
  echo "script-helpers is missing; run: git submodule update --init --recursive" >&2
  exit 1
fi
# shellcheck source=scripts/script-helpers/helpers.sh
source "$helpers"
shlib_import logging docker

print_info "Checking InkMate"

if command -v python3 >/dev/null 2>&1; then
  print_info "Validating documentation image paths"
  python3 scripts/check_doc_assets.py
else
  log_warn "Python unavailable; documentation image validation skipped"
fi

if command -v python3 >/dev/null 2>&1 && [[ -d gateway/tests ]]; then
  print_info "Running gateway tests"
  python3 -m pytest gateway/tests
fi

if command -v idf.py >/dev/null 2>&1 && [[ -f firmware/CMakeLists.txt ]]; then
  for profile in v1 v2; do
    SDKCONFIG_DEFAULTS="sdkconfig.defaults;sdkconfig.$profile" \
      idf.py -C firmware -B "firmware/build/$profile" build
  done
else
  log_warn "ESP-IDF or firmware project unavailable; firmware builds skipped"
fi

if command -v docker >/dev/null 2>&1 && [[ -f gateway/Dockerfile ]]; then
  print_info "Validating Compose configuration"
  docker_compose config --quiet
else
  log_warn "Docker or gateway Dockerfile unavailable; Compose validation skipped"
fi

print_success "Available checks passed"
