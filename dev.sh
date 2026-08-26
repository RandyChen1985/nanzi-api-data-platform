#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_PORT=8000

usage() {
    cat <<'EOF'
用法:
  ./dev.sh              前台启动开发服务
  ./dev.sh -d           后台启动开发服务
  ./dev.sh --daemon     后台启动开发服务
EOF
}

read_port_from_env() {
    local env_file="${1:-${REPO_ROOT}/.env}"
    local port

    if [[ ! -f "${env_file}" ]]; then
        printf '%s\n' "${DEFAULT_PORT}"
        return 0
    fi

    port="$(grep -E '^[[:space:]]*API_SERVICE_PORT[[:space:]]*=' "${env_file}" \
        | tail -n 1 \
        | cut -d '=' -f2- \
        | sed -E "s/[[:space:]]+#.*$//; s/^[[:space:]]+//; s/[[:space:]]+$//; s/^[\"']//; s/[\"']$//" \
        || true)"

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

main() {
    local daemon_mode
    local port
    local pid
    local python_cmd
    local package_hash
    local needs_install
    local hash_file
    local node_modules_missing
    local arg

    for arg in "$@"; do
        if [[ "${arg}" == "-h" || "${arg}" == "--help" ]]; then
            usage
            return 0
        fi
    done

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
    echo "🧹 [1/3] 清理旧构建和日志..."
    rm -rf frontend/dist app.log
    echo "✅ 清理完成。"

    echo ""
    echo "🚀 [2/3] 准备并编译前端..."
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

    echo ""
    echo "🛑 [3/3] 检查并停止旧服务（端口 ${port}）..."
    pid="$(lsof -t -i:"${port}" || true)"
    if [[ -n "${pid}" ]]; then
        kill -9 ${pid}
        echo "✅ 已停止旧进程（PID: ${pid}）"
    else
        echo "ℹ️  端口 ${port} 空闲，无需停止旧服务。"
    fi

    if [[ -x "venv/bin/python" ]]; then
        python_cmd="venv/bin/python"
    elif [[ -x ".venv/bin/python" ]]; then
        python_cmd=".venv/bin/python"
    else
        python_cmd="python3"
    fi

    if [[ "${daemon_mode}" == "true" ]]; then
        echo "🔥 后台启动后端服务..."
        nohup "${python_cmd}" -m uvicorn app.main:app \
            --host 0.0.0.0 \
            --port "${port}" \
            --reload \
            > app.log 2>&1 &
        echo "✅ 后端服务已在后台启动（PID: $!）"
        echo "   访问端口: http://0.0.0.0:${port}"
        echo "   日志文件: app.log"
        echo "   实时日志: tail -f app.log"
    else
        echo "🔥 前台启动后端服务..."
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
