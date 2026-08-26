# dev.sh 前后台启动支持 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让数据服务平台的 `dev.sh` 支持 `.env` 端口、前端依赖自动检查，以及默认前台和 `-d`/`--daemon` 后台启动。

**Architecture:** 将启动脚本拆成可独立验证的参数解析、`.env` 端口解析、依赖校验和主启动流程。脚本固定切换到自身所在仓库根目录，避免从其他工作目录调用时找不到 `frontend` 或 `.env`；后台模式仅改变 Uvicorn 的进程承载方式。

**Tech Stack:** Bash、Uvicorn、npm、pytest-compatible shell regression script.

---

### Task 1: 建立 dev.sh 行为回归测试

**Files:**
- Create: `tests/scripts/test_dev_sh.sh`

- [x] **Step 1: Write the failing test**

创建 Bash 测试脚本，source `dev.sh` 的测试安全函数，验证新接口：

```bash
#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
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
```

- [x] **Step 2: Run it to verify it fails**

Run: `bash tests/scripts/test_dev_sh.sh`

Expected: FAIL because the current `dev.sh` does not expose the tested parsing and dependency-check functions.

### Task 2: 实现 dev.sh 前台/后台启动与端口、依赖检查

**Files:**
- Modify: `dev.sh`

- [x] **Step 1: Write minimal implementation**

实现以下函数和流程：

```bash
read_port_from_env() { ...; }
validate_port() { ...; }
parse_daemon_mode() { ...; }
needs_npm_install() { ...; }
main() { ...; }

if [[ "${DEV_SH_SOURCE_ONLY:-0}" != "1" ]]; then
    main "$@"
fi
```

`main` 负责清理、停止配置端口旧进程、检查并安装 `frontend` 依赖、构建前端、选择 Python、再根据 daemon 标志选择 `nohup ... > app.log 2>&1 &` 或前台执行。`.env` 只读取 `API_SERVICE_PORT` 的最后一个有效赋值，不执行文件内容；前端校验值使用 `cksum package.json`，写入 `frontend/node_modules/.package_hash`。

- [x] **Step 2: Run focused tests to verify it passes**

Run: `bash tests/scripts/test_dev_sh.sh`

Expected: PASS。

- [x] **Step 3: Check shell syntax**

Run: `bash -n dev.sh tests/scripts/test_dev_sh.sh`

Expected: exit code 0。

### Task 3: 同步开发文档

**Files:**
- Modify: `README.md:214-220`

- [x] **Step 1: Update the usage contract**

将一键开发说明改为明确列出：默认前台运行、`./dev.sh -d` 后台运行、端口从 `.env` 的 `API_SERVICE_PORT` 读取且默认 `8000`，并说明前端依赖缺失或 `package.json` 变化时会自动执行 `npm install`。

- [x] **Step 2: Verify the documentation matches the script**

Run: `rg -n "dev\.sh|API_SERVICE_PORT|npm install|前台|后台" README.md dev.sh`

Expected: 文档中的命令、端口和模式与脚本实现一致，没有继续描述“默认后台启动”。

### Task 4: 运行比例适当的集成验证

**Files:**
- No source changes.

- [x] **Step 1: Confirm the repository diff is scoped**

Run: `git status --short && git diff --check -- dev.sh README.md tests/scripts/test_dev_sh.sh`

Expected: 只包含本任务文件；没有 whitespace error。保留工作区中原有的无关改动。

- [x] **Step 2: Exercise the real frontend preparation path**

Run: `./dev.sh -d`

Expected: 依赖已存在时跳过 `npm install`，前端构建成功，脚本立即返回并输出 PID、端口和 `app.log`；随后用 `lsof -ti:<API_SERVICE_PORT>` 检查服务已监听，再手动停止该 PID。若本机依赖或数据库/Redis环境不满足，只记录对应阻断，不修改业务配置。本次实际验证中，前端流程通过；后端因虚拟环境缺少未声明的 `python-multipart` 在应用导入阶段退出，未能完成监听验证。
