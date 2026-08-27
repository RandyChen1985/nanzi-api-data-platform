#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_PORT=8000
PYTHON_VERSION="3.11"
VENV_DIR="${REPO_ROOT}/.venv"
VENV_PYTHON="${VENV_DIR}/bin/python"
REQUIREMENTS_FILE="${REPO_ROOT}/requirements.txt"
REQUIREMENTS_HASH_FILE="${VENV_DIR}/.requirements.hash"
SERVICE_PID_FILE="${REPO_ROOT}/.dev-server.pid"
UV_CMD=""

usage() {
    cat <<'EOF'
用法:
  ./dev.sh              前台启动开发服务
  ./dev.sh -d           后台启动开发服务
  ./dev.sh --daemon     后台启动开发服务
  ./dev.sh status       检查后台开发服务状态
  ./dev.sh stop         停止后台开发服务
EOF
}

read_env_value() {
    local key="$1"
    local env_file="${2:-${REPO_ROOT}/.env}"

    if [[ ! -f "${env_file}" ]]; then
        return 0
    fi

    grep -E "^[[:space:]]*${key}[[:space:]]*=" "${env_file}" \
        | tail -n 1 \
        | cut -d '=' -f2- \
        | sed -E "s/[[:space:]]+#.*$//; s/^[[:space:]]+//; s/[[:space:]]+$//; s/^[\"']//; s/[\"']$//" \
        || true
}

redact_url() {
    printf '%s' "$1" | sed -E 's#(https?://)([^/@]+@)#\1***@#'
}

read_port_from_env() {
    local env_file="${1:-${REPO_ROOT}/.env}"
    local port

    if [[ ! -f "${env_file}" ]]; then
        printf '%s\n' "${DEFAULT_PORT}"
        return 0
    fi

    port="$(read_env_value API_SERVICE_PORT "${env_file}")"

    printf '%s\n' "${port:-${DEFAULT_PORT}}"
}

validate_port() {
    local port="$1"
    local normalized

    if [[ ! "${port}" =~ ^[0-9]+$ ]]; then
        echo "❌ API_SERVICE_PORT 必须是 1-65535 的整数：${port}" >&2
        return 1
    fi

    normalized="$(printf '%s' "${port}" | sed -E 's/^0+//')"
    normalized="${normalized:-0}"
    if (( normalized < 1 || normalized > 65535 )); then
        echo "❌ API_SERVICE_PORT 必须是 1-65535 的整数：${port}" >&2
        return 1
    fi
}

parse_daemon_mode() {
    local daemon_mode=false
    local arg

    for arg in "$@"; do
        case "${arg}" in
            -d|--daemon)
                daemon_mode=true
                ;;
            -h|--help)
                echo "不应直接调用 parse_daemon_mode 处理帮助参数" >&2
                return 2
                ;;
            *)
                echo "❌ 未知参数：${arg}（支持 -d 或 --daemon）" >&2
                return 2
                ;;
        esac
    done

    printf '%s\n' "${daemon_mode}"
}

needs_npm_install() {
    local node_modules_missing="$1"
    local current_hash="$2"
    local hash_file="$3"
    local saved_hash=""

    if [[ -f "${hash_file}" ]]; then
        saved_hash="$(cat "${hash_file}")"
    fi

    if [[ "${node_modules_missing}" == "true" || ! -f "${hash_file}" || "${current_hash}" != "${saved_hash}" ]]; then
        printf 'true\n'
    else
        printf 'false\n'
    fi
}

backend_env_dir() {
    local repo_root="${1:-${REPO_ROOT}}"

    printf '%s\n' "${repo_root}/.venv"
}

needs_backend_install() {
    local current_hash="$1"
    local hash_file="$2"
    local saved_hash=""

    if [[ -f "${hash_file}" ]]; then
        saved_hash="$(cat "${hash_file}")"
    fi

    if [[ ! -f "${hash_file}" || "${current_hash}" != "${saved_hash}" ]]; then
        printf 'true\n'
    else
        printf 'false\n'
    fi
}

backend_runtime_ready() {
    local python_cmd="$1"

    "${python_cmd}" -c 'import fastapi, uvicorn' >/dev/null 2>&1
}

backend_pip_index_url() {
    printf '%s\n' "${PYPI_INDEX_URL:-${PIP_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}}"
}

require_lsof() {
    if ! command -v lsof >/dev/null 2>&1; then
        echo "❌ 未找到 lsof，无法安全检查开发服务端口。" >&2
        return 1
    fi
}

service_listener_pids() {
    local port="$1"

    lsof -nP -t -iTCP:"${port}" -sTCP:LISTEN 2>/dev/null || true
}

collect_live_listener_pids() {
    local listener_pids="${1:-}"
    local candidate

    while read -r candidate; do
        [[ -n "${candidate}" ]] || continue
        if kill -0 "${candidate}" 2>/dev/null; then
            printf '%s\n' "${candidate}"
        fi
    done <<< "${listener_pids}"
}

service_pid_file_pid() {
    local pid_file_pid=""

    if [[ -f "${SERVICE_PID_FILE}" ]]; then
        pid_file_pid="$(cat "${SERVICE_PID_FILE}" 2>/dev/null || true)"
    fi
    if [[ "${pid_file_pid}" =~ ^[0-9]+$ ]]; then
        printf '%s\n' "${pid_file_pid}"
    fi
}

service_process_is_descendant_of() {
    local process_pid="$1"
    local ancestor_pid="$2"
    local parent_pid

    while [[ "${process_pid}" =~ ^[0-9]+$ && "${process_pid}" != "1" ]]; do
        parent_pid="$(ps -p "${process_pid}" -o ppid= 2>/dev/null | tr -d '[:space:]')"
        if [[ ! "${parent_pid}" =~ ^[0-9]+$ || "${parent_pid}" == "${process_pid}" ]]; then
            return 1
        fi
        if [[ "${parent_pid}" == "${ancestor_pid}" ]]; then
            return 0
        fi
        process_pid="${parent_pid}"
    done

    return 1
}

service_process_belongs_to_managed_service() {
    local process_pid="$1"
    local port="$2"
    local managed_pid

    if service_process_matches "${process_pid}" "${port}"; then
        return 0
    fi

    managed_pid="$(service_pid_file_pid)"
    if [[ -z "${managed_pid}" || "${managed_pid}" == "${process_pid}" ]] \
        || ! kill -0 "${managed_pid}" 2>/dev/null \
        || ! service_process_matches "${managed_pid}" "${port}"; then
        return 1
    fi

    service_process_is_descendant_of "${process_pid}" "${managed_pid}"
}

service_process_matches() {
    local pid="$1"
    local port="$2"
    local process_command

    process_command="$(ps -p "${pid}" -o command= 2>/dev/null || true)"
    [[ "${process_command}" == *"uvicorn"* \
        && "${process_command}" == *"app.main:app"* \
        && "${process_command}" == *"--port ${port}"* ]]
}

collect_managed_listener_pids() {
    local port="$1"
    local listener_pids="${2:-}"
    local candidate

    while read -r candidate; do
        [[ -n "${candidate}" ]] || continue
        if kill -0 "${candidate}" 2>/dev/null \
            && service_process_belongs_to_managed_service "${candidate}" "${port}"; then
            printf '%s\n' "${candidate}"
        fi
    done <<< "${listener_pids}"
}

collect_unmanaged_listener_pids() {
    local port="$1"
    local listener_pids="${2:-}"
    local candidate

    while read -r candidate; do
        [[ -n "${candidate}" ]] || continue
        if kill -0 "${candidate}" 2>/dev/null \
            && ! service_process_belongs_to_managed_service "${candidate}" "${port}"; then
            printf '%s\n' "${candidate}"
        fi
    done <<< "${listener_pids}"
}

collect_managed_service_pids() {
    local port="$1"
    local listener_pids="${2:-}"
    local candidate
    local seen_pids=" "

    while read -r candidate; do
        [[ -n "${candidate}" ]] || continue
        if [[ "${seen_pids}" != *" ${candidate} "* ]]; then
            seen_pids+="${candidate} "
            printf '%s\n' "${candidate}"
        fi
    done < <(collect_managed_listener_pids "${port}" "${listener_pids}")

    candidate="$(service_pid_file_pid)"
    if [[ -n "${candidate}" ]] \
        && kill -0 "${candidate}" 2>/dev/null \
        && service_process_matches "${candidate}" "${port}" \
        && [[ "${seen_pids}" != *" ${candidate} "* ]]; then
        printf '%s\n' "${candidate}"
    fi
}

collect_live_pids() {
    local pids="${1:-}"
    local candidate

    while read -r candidate; do
        [[ -n "${candidate}" ]] || continue
        if kill -0 "${candidate}" 2>/dev/null; then
            printf '%s\n' "${candidate}"
        fi
    done <<< "${pids}"
}

status_service() {
    local port
    local listener_pids
    local managed_listener_pids
    local managed_service_pids
    local unmanaged_listener_pids

    port="$(read_port_from_env "${REPO_ROOT}/.env")"
    validate_port "${port}"
    require_lsof

    listener_pids="$(collect_live_listener_pids "$(service_listener_pids "${port}")")"
    managed_listener_pids="$(collect_managed_listener_pids "${port}" "${listener_pids}")"
    managed_service_pids="$(collect_managed_service_pids "${port}" "${listener_pids}")"
    unmanaged_listener_pids="$(collect_unmanaged_listener_pids "${port}" "${listener_pids}")"

    echo "🔎 开发服务状态（端口 ${port}）"
    if [[ -n "${managed_listener_pids}" ]]; then
        echo "✅ 开发服务正在运行（监听 PID: ${managed_listener_pids//$'\n'/, }）"
        echo "   日志文件: ${REPO_ROOT}/app.log"
        if [[ -n "${unmanaged_listener_pids}" ]]; then
            echo "⚠️  端口同时被其他进程占用（PID: ${unmanaged_listener_pids//$'\n'/, }）" >&2
        fi
        return 0
    fi

    if [[ -n "${managed_service_pids}" ]]; then
        echo "⏳ 开发服务进程已存在，但端口 ${port} 尚未监听（PID: ${managed_service_pids//$'\n'/, }）"
        return 1
    fi

    if [[ -n "${listener_pids}" ]]; then
        echo "⚠️ 端口 ${port} 被其他进程占用（PID: ${unmanaged_listener_pids//$'\n'/, }）" >&2
    elif [[ -f "${SERVICE_PID_FILE}" ]]; then
        echo "⚠️ 发现失效的 PID 文件：${SERVICE_PID_FILE}"
        echo "ℹ️  开发服务当前未运行。"
    else
        echo "ℹ️  开发服务当前未运行，端口 ${port} 空闲。"
    fi
    return 1
}

stop_service() {
    local port
    local listener_pids
    local managed_service_pids
    local unmanaged_listener_pids
    local remaining_listener_pids
    local remaining_managed_pids
    local pid

    port="$(read_port_from_env "${REPO_ROOT}/.env")"
    validate_port "${port}"
    require_lsof

    listener_pids="$(collect_live_listener_pids "$(service_listener_pids "${port}")")"
    managed_service_pids="$(collect_managed_service_pids "${port}" "${listener_pids}")"
    unmanaged_listener_pids="$(collect_unmanaged_listener_pids "${port}" "${listener_pids}")"

    if [[ -n "${unmanaged_listener_pids}" ]]; then
        echo "❌ 端口 ${port} 存在非 dev.sh 进程（PID: ${unmanaged_listener_pids//$'\n'/, }），拒绝停止。" >&2
        return 1
    fi

    if [[ -z "${managed_service_pids}" ]]; then
        if [[ -f "${SERVICE_PID_FILE}" ]]; then
            rm -f "${SERVICE_PID_FILE}"
            echo "⚠️  已清理失效的 PID 文件：${SERVICE_PID_FILE}"
        fi
        echo "ℹ️  开发服务当前未运行，端口 ${port} 空闲。"
        return 0
    fi

    echo "🛑 正在停止开发服务（端口 ${port}，PID: ${managed_service_pids//$'\n'/, }）..."
    for pid in ${managed_service_pids}; do
        kill "${pid}" 2>/dev/null || true
    done
    sleep 2

    remaining_listener_pids="$(collect_live_listener_pids "$(service_listener_pids "${port}")")"
    remaining_managed_pids="$(collect_live_pids "${managed_service_pids}")"
    if [[ -n "${remaining_managed_pids}" ]]; then
        echo "⚠️ 进程仍在运行，正在强制停止（PID: ${remaining_managed_pids//$'\n'/, }）..."
        for pid in ${remaining_managed_pids}; do
            kill -9 "${pid}" 2>/dev/null || true
        done
        sleep 1
        remaining_listener_pids="$(collect_live_listener_pids "$(service_listener_pids "${port}")")"
        remaining_managed_pids="$(collect_live_pids "${managed_service_pids}")"
    fi

    if [[ -n "${remaining_managed_pids}" || -n "${remaining_listener_pids}" ]]; then
        echo "❌ 未能完全停止端口 ${port} 上的开发服务。" >&2
        return 1
    fi

    rm -f "${SERVICE_PID_FILE}"
    echo "✅ 开发服务已停止，端口 ${port} 已释放。"
}

find_uv() {
    local candidate

    if command -v uv >/dev/null 2>&1; then
        UV_CMD="$(command -v uv)"
        return 0
    fi

    if [[ -n "${HOME:-}" ]]; then
        for candidate in "${HOME}/.local/bin/uv" "${HOME}/.cargo/bin/uv"; do
            if [[ -x "${candidate}" ]]; then
                UV_CMD="${candidate}"
                return 0
            fi
        done
    fi

    return 1
}

ensure_uv() {
    if find_uv; then
        return 0
    fi

    echo "📦 未检测到 uv，正在通过官方安装脚本自动安装..." >&2
    if command -v curl >/dev/null 2>&1; then
        if ! curl -LsSf https://astral.sh/uv/install.sh | sh >&2; then
            echo "❌ uv 自动安装失败，请检查网络后重试。" >&2
            return 1
        fi
    elif command -v wget >/dev/null 2>&1; then
        if ! wget -qO- https://astral.sh/uv/install.sh | sh >&2; then
            echo "❌ uv 自动安装失败，请检查网络后重试。" >&2
            return 1
        fi
    else
        echo "❌ 未找到 curl 或 wget，无法自动安装 uv；请先安装其中一个工具。" >&2
        return 1
    fi

    if ! find_uv; then
        echo "❌ uv 安装完成但当前脚本无法定位 uv，请重新打开终端后重试。" >&2
        return 1
    fi

    echo "✅ uv 已准备完成：${UV_CMD}" >&2
}

prepare_python_environment() {
    local current_version=""
    local current_hash
    local pip_index_url

    if [[ ! -f "${REQUIREMENTS_FILE}" ]]; then
        echo "❌ 未找到后端依赖文件：${REQUIREMENTS_FILE}" >&2
        return 1
    fi

    ensure_uv
    echo "🧰 [1/4] 正在准备 uv、Python ${PYTHON_VERSION} 和后端依赖..." >&2

    if [[ -x "${VENV_PYTHON}" ]]; then
        current_version="$("${VENV_PYTHON}" -c 'import sys; print(".".join(map(str, sys.version_info[:2])))' 2>/dev/null || true)"
    fi

    if [[ "${current_version}" != "${PYTHON_VERSION}" ]]; then
        echo "🐍 正在准备 Python ${PYTHON_VERSION}..." >&2
        "${UV_CMD}" python install "${PYTHON_VERSION}" >&2

        if [[ -L "${VENV_DIR}" ]]; then
            echo "❌ 错误：${VENV_DIR} 是符号链接，拒绝自动清理。" >&2
            return 1
        fi

        if [[ -e "${VENV_DIR}" ]]; then
            echo "♻️ 检测到 ${VENV_DIR} 不是 Python ${PYTHON_VERSION}，正在安全重建..." >&2
            "${UV_CMD}" venv --clear --python "${PYTHON_VERSION}" "${VENV_DIR}" >&2
        else
            echo "📁 正在创建 Python ${PYTHON_VERSION} 虚拟环境：${VENV_DIR}" >&2
            "${UV_CMD}" venv --python "${PYTHON_VERSION}" "${VENV_DIR}" >&2
        fi
    else
        echo "✅ 已复用 Python ${PYTHON_VERSION} 虚拟环境" >&2
    fi

    if [[ ! -x "${VENV_PYTHON}" ]]; then
        echo "❌ Python 虚拟环境创建失败：未找到 ${VENV_PYTHON}" >&2
        return 1
    fi

    current_version="$("${VENV_PYTHON}" -c 'import sys; print(".".join(map(str, sys.version_info[:2])))' 2>/dev/null || true)"
    if [[ "${current_version}" != "${PYTHON_VERSION}" ]]; then
        echo "❌ Python 版本校验失败：期望 ${PYTHON_VERSION}，实际 ${current_version:-未知}" >&2
        return 1
    fi

    current_hash="$(cksum "${REQUIREMENTS_FILE}" | awk '{print $1 ":" $2}')"
    pip_index_url="$(backend_pip_index_url)"
    if [[ "$(needs_backend_install "${current_hash}" "${REQUIREMENTS_HASH_FILE}")" == "true" ]] || ! backend_runtime_ready "${VENV_PYTHON}"; then
        echo "📦 正在使用 PyPI 镜像安装后端依赖..." >&2
        if ! "${UV_CMD}" pip install --python "${VENV_PYTHON}" --default-index "${pip_index_url}" -r "${REQUIREMENTS_FILE}" >&2; then
            echo "❌ 后端依赖安装失败，请检查服务器网络和 pip 错误信息。" >&2
            echo "   手动重试：${UV_CMD} pip install --python ${VENV_PYTHON} --default-index <镜像地址> -r ${REQUIREMENTS_FILE}" >&2
            return 1
        fi
        if ! backend_runtime_ready "${VENV_PYTHON}"; then
            echo "❌ 后端依赖安装完成，但 FastAPI/Uvicorn 仍无法导入。" >&2
            return 1
        fi
        printf '%s\n' "${current_hash}" > "${REQUIREMENTS_HASH_FILE}"
        echo "✅ 后端依赖安装完成。" >&2
    else
        if ! "${UV_CMD}" pip check --python "${VENV_PYTHON}" >&2; then
            echo "❌ 后端依赖检查失败，请修复 ${REQUIREMENTS_FILE} 对应的环境后重试。" >&2
            return 1
        fi
        echo "✅ 后端依赖未变化且环境检查通过，跳过安装。" >&2
    fi

    if ! backend_runtime_ready "${VENV_PYTHON}"; then
        echo "❌ 后端运行环境检查失败：${VENV_PYTHON} 无法导入 fastapi/uvicorn。" >&2
        return 1
    fi

    printf '%s\n' "${VENV_PYTHON}"
}

print_runtime_environment() {
    local database_type_configured="${DATABASE_TYPE:-$(read_env_value DATABASE_TYPE)}"
    local database_type_normalized
    local database_type_effective
    local database_host
    local database_port
    local database_name
    local redis_host="${REDIS_HOST:-$(read_env_value REDIS_HOST)}"
    local redis_port="${REDIS_PORT:-$(read_env_value REDIS_PORT)}"
    local redis_db="${REDIS_DB:-$(read_env_value REDIS_DB)}"
    local redis_enable="${REDIS_ENABLE:-$(read_env_value REDIS_ENABLE)}"

    database_type_configured="${database_type_configured:-mysql}"
    database_type_normalized="$(printf '%s' "${database_type_configured}" | tr '[:upper:]' '[:lower:]')"
    case "${database_type_normalized}" in
        mysql|mariadb)
            database_type_effective="mysql"
            database_host="${MYSQL_HOST:-$(read_env_value MYSQL_HOST)}"
            database_port="${MYSQL_PORT:-$(read_env_value MYSQL_PORT)}"
            database_name="${MYSQL_DB:-$(read_env_value MYSQL_DB)}"
            database_host="${database_host:-localhost}"
            database_port="${database_port:-3306}"
            ;;
        *)
            database_type_effective="unsupported"
            database_host="未配置"
            database_port="未配置"
            database_name="未配置"
            ;;
    esac
    database_name="${database_name:-未配置}"
    redis_host="${redis_host:-localhost}"
    redis_port="${redis_port:-6379}"
    redis_db="${redis_db:-0}"
    redis_enable="$(printf '%s' "${redis_enable:-true}" | tr '[:upper:]' '[:lower:]')"

    echo "➜ DATABASE_TYPE: ${database_type_configured} (effective: ${database_type_effective})"
    echo "➜ 数据库地址: ${database_host}:${database_port}/${database_name}"
    if [[ "${redis_enable}" == "false" || "${redis_enable}" == "0" || "${redis_enable}" == "no" || "${redis_enable}" == "off" ]]; then
        echo "➜ Redis 地址: 已禁用"
    else
        echo "➜ Redis 地址: ${redis_host}:${redis_port}/${redis_db}"
    fi
}

main() {
    local daemon_mode
    local port
    local pid
    local python_cmd
    local package_hash
    local needs_install
    local hash_file
    local node_modules_missing
    local backend_python_cmd
    local uv_version
    local arg

    for arg in "$@"; do
        if [[ "${arg}" == "-h" || "${arg}" == "--help" ]]; then
            usage
            return 0
        fi
    done

    if [[ "${1:-}" == "status" || "${1:-}" == "stop" ]]; then
        if [[ "$#" -ne 1 ]]; then
            echo "❌ status/stop 不接受额外参数。" >&2
            usage >&2
            return 2
        fi
        if [[ "${1}" == "status" ]]; then
            status_service
        else
            stop_service
        fi
        return "$?"
    fi

    daemon_mode="$(parse_daemon_mode "$@")"
    port="$(read_port_from_env "${REPO_ROOT}/.env")"
    validate_port "${port}"

    cd "${REPO_ROOT}"

    echo "=================================================="
    echo "       NanZi 数据服务平台 · 本地开发启动工具"
    echo "       用法: ./dev.sh (前台调试) | ./dev.sh -d (后台常驻)"
    echo "       端口: ${port}"
    echo "=================================================="

    echo ""
    echo "启动环境信息"
    if find_uv; then
        uv_version="$("${UV_CMD}" --version 2>/dev/null || echo "版本未知")"
    else
        uv_version="未安装（启动时自动安装）"
    fi
    echo "➜ uv: ${uv_version}"
    echo "➜ Python 目标版本: ${PYTHON_VERSION}"
    echo "➜ 虚拟环境: .venv"
    echo "➜ PyPI 镜像: $(redact_url "$(backend_pip_index_url)")"
    print_runtime_environment

    echo ""
    backend_python_cmd="$(prepare_python_environment)"
    echo "✅ 后端运行环境已就绪：${backend_python_cmd}"

    echo ""
    echo "🛑 [2/4] 检查并停止旧服务（端口 ${port}）..."
    stop_service

    echo ""
    echo "🧹 清理旧构建和日志..."
    rm -rf frontend/dist app.log
    echo "✅ 清理完成。"

    echo ""
    echo "🚀 [3/4] 准备并编译前端..."
    if [[ ! -d "frontend" || ! -f "frontend/package.json" ]]; then
        echo "❌ 未找到 frontend/package.json" >&2
        return 1
    fi

    cd frontend
    package_hash="$(cksum package.json)"
    hash_file="node_modules/.package_hash"
    if [[ -d node_modules ]]; then
        node_modules_missing=false
    else
        node_modules_missing=true
    fi
    needs_install="$(needs_npm_install "${node_modules_missing}" "${package_hash}" "${hash_file}")"

    if [[ "${needs_install}" == "true" ]]; then
        echo "📦 检测到前端依赖未安装或 package.json 已变化，执行 npm install..."
        npm install
        mkdir -p node_modules
        printf '%s\n' "${package_hash}" > "${hash_file}"
        echo "✅ 前端依赖安装完成。"
    else
        echo "✅ 前端依赖已是最新，跳过 npm install。"
    fi

    npm run build
    cd "${REPO_ROOT}"
    echo "✅ 前端编译完成。"

    python_cmd="${backend_python_cmd}"

    if [[ "${daemon_mode}" == "true" ]]; then
        echo "🔥 [4/4] 后台启动后端服务..."
        nohup "${python_cmd}" -m uvicorn app.main:app \
            --host 0.0.0.0 \
            --port "${port}" \
            --reload \
            > app.log 2>&1 &
        local server_pid="$!"
        printf '%s\n' "${server_pid}" > "${SERVICE_PID_FILE}"
        echo "✅ 后端服务已在后台启动（PID: ${server_pid}）"
        echo "   访问端口: http://0.0.0.0:${port}"
        echo "   日志文件: app.log"
        echo "   实时日志: tail -f app.log"
    else
        echo "🔥 [4/4] 前台启动后端服务..."
        echo "提示：按 Ctrl+C 停止服务；后台运行请使用 ./dev.sh -d"
        echo "------------------------------------------------"
        "${python_cmd}" -m uvicorn app.main:app \
            --host 0.0.0.0 \
            --port "${port}" \
            --reload
    fi
}

if [[ "${DEV_SH_SOURCE_ONLY:-0}" != "1" ]]; then
    main "$@"
fi
