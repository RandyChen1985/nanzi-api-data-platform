#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# Fail before sourcing an implementation without a source-only entry point, so
# this test cannot clean the real frontend build or start a service.
grep -q 'DEV_SH_SOURCE_ONLY' "${REPO_ROOT}/dev.sh"

export DEV_SH_SOURCE_ONLY=1
# shellcheck disable=SC1091
source "${REPO_ROOT}/dev.sh"

assert_eq() {
    [[ "$1" == "$2" ]] || { echo "expected <$2>, got <$1>" >&2; exit 1; }
}

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

printf 'API_SERVICE_PORT=8123\n' > "${tmp_dir}/.env"
assert_eq "$(read_port_from_env "${tmp_dir}/.env")" "8123"
assert_eq "$(read_port_from_env "${tmp_dir}/missing.env")" "8000"
printf 'API_SERVICE_PORT=70000\n' > "${tmp_dir}/bad.env"
if validate_port "$(read_port_from_env "${tmp_dir}/bad.env")"; then
    echo "invalid port was accepted" >&2
    exit 1
fi

assert_eq "$(parse_daemon_mode)" "false"
assert_eq "$(parse_daemon_mode -d)" "true"
assert_eq "$(parse_daemon_mode --daemon)" "true"

printf 'package-json-hash\n' > "${tmp_dir}/.package_hash"
assert_eq "$(needs_npm_install false package-json-hash "${tmp_dir}/.package_hash")" "false"
assert_eq "$(needs_npm_install false changed-hash "${tmp_dir}/.package_hash")" "true"
assert_eq "$(needs_npm_install true changed-hash "${tmp_dir}/.package_hash")" "true"
