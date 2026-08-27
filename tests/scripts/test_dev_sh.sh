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

mkdir -p "${tmp_dir}/venv/bin"
touch "${tmp_dir}/venv/bin/python"
chmod +x "${tmp_dir}/venv/bin/python"
assert_eq "$(backend_env_dir "${tmp_dir}")" "${tmp_dir}/.venv"
mkdir -p "${tmp_dir}/.venv/bin"
touch "${tmp_dir}/.venv/bin/python"
chmod +x "${tmp_dir}/.venv/bin/python"
assert_eq "$(backend_env_dir "${tmp_dir}")" "${tmp_dir}/.venv"

printf 'requirements-hash\n' > "${tmp_dir}/.backend_requirements_hash"
assert_eq "$(needs_backend_install requirements-hash "${tmp_dir}/.backend_requirements_hash")" "false"
assert_eq "$(needs_backend_install changed-hash "${tmp_dir}/.backend_requirements_hash")" "true"
assert_eq "$(needs_backend_install requirements-hash "${tmp_dir}/missing.hash")" "true"

unset PYPI_INDEX_URL
unset PIP_INDEX_URL
assert_eq "$(backend_pip_index_url)" "https://pypi.tuna.tsinghua.edu.cn/simple"
PIP_INDEX_URL="https://pypi.example.com/simple"
assert_eq "$(backend_pip_index_url)" "https://pypi.example.com/simple"
PYPI_INDEX_URL="https://pypi.example.cn/simple"
assert_eq "$(backend_pip_index_url)" "https://pypi.example.cn/simple"
assert_eq "$(redact_url "https://build-user:build-secret@example.com/simple")" "https://***@example.com/simple"

control_dir="$(mktemp -d)"
control_pid=""
trap 'if [[ -n "${control_pid:-}" ]] && kill -0 "${control_pid}" 2>/dev/null; then kill "${control_pid}" 2>/dev/null || true; fi; rm -rf "${tmp_dir}" "${control_dir}"' EXIT
printf 'API_SERVICE_PORT=8123\n' > "${control_dir}/.env"
REPO_ROOT="${control_dir}"
SERVICE_PID_FILE="${control_dir}/.dev-server.pid"

sleep 60 &
control_pid="$!"
printf '%s\n' "${control_pid}" > "${SERVICE_PID_FILE}"
service_listener_pids() {
    printf '%s\n' "${control_pid}"
}
service_process_matches() {
    [[ "$1" == "${control_pid}" && "$2" == "8123" ]]
}

status_output=""
if ! status_output="$(status_service 2>&1)"; then
    echo "status_service should report the managed service as running: ${status_output}" >&2
    exit 1
fi
[[ "${status_output}" == *"正在运行"* ]] || {
    echo "status_service did not report a running service: ${status_output}" >&2
    exit 1
}

if ! stop_service >/dev/null 2>&1; then
    echo "stop_service should stop the managed service" >&2
    exit 1
fi
if kill -0 "${control_pid}" 2>/dev/null; then
    echo "stop_service left the managed process alive" >&2
    exit 1
fi
wait "${control_pid}" 2>/dev/null || true
[[ ! -e "${SERVICE_PID_FILE}" ]] || {
    echo "stop_service left a stale PID file" >&2
    exit 1
}

sleep 60 &
control_pid="$!"
service_listener_pids() {
    printf '%s\n' "${control_pid}"
}
service_process_matches() {
    return 1
}
if stop_service >/dev/null 2>&1; then
    echo "stop_service should refuse an unrelated process" >&2
    exit 1
fi
kill -0 "${control_pid}" 2>/dev/null || {
    echo "stop_service killed an unrelated process" >&2
    exit 1
}
kill "${control_pid}" 2>/dev/null || true
wait "${control_pid}" 2>/dev/null || true
control_pid=""
