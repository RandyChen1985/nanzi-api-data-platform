# 云枢数据服务平台部署安装指南 (HOW TO INSTALL)

本指南旨在指导开发和运维人员在本地开发环境或生产环境下完成 **云枢 · 数据服务平台 (Yunshu API Data Platform)** 的安装部署、数据库表结构初始化以及常见问题的快速排查。

---

## 1. 概要 (Overview)

云枢数据服务平台是企业级的 Data API 与元数据治理中枢，将物理表、自定义 SQL 与语义元数据封装为可治理、可审计的 RESTful API。

为适应不同用户环境，平台主要提供两套部署方案：

*   **Docker 容器化部署（生产首选，支持离线）**：通过版本号参数构建 Docker 归档包，在隔离容器环境中运行并一键部署。
*   **本地源码开发调试部署（开发首选）**：使用 Python 虚拟环境与 Node.js 宿主机环境，支持前后端热重载实时联调。

无论采用何种方案，服务拉起前均需完成 **MySQL 数据库结构与初始管理员账号** 的导入。

---

## 2. 前置环境 (Prerequisites)

### 💻 基础工具依赖

*   **Docker**（建议 v20.10+）与 **Docker Compose**（建议 v2.0.0+）
*   **Python**（建议 3.10+，仅用于本地源码调试或运行 SQL 导入工具；若直接使用已打好的 Docker 镜像包部署，则无需安装）
*   **Node.js**（建议 18+ & npm，仅用于本地开发联调或宿主机前端预构建；若不自行构建镜像且不进行本地源码调试，则无需安装）

### 🔌 数据库与外部依赖服务

*   **MySQL**（建议 8.0+）：必须支持 `utf8mb4` 字符集，用于存放平台系统配置、用户权限、元数据、审计日志等。
*   **Redis**（建议 6.0+，可选但推荐）：用于缓存、限流与异步任务调度；生产环境建议开启 `REDIS_ENABLE=true`。
*   **ClickHouse / Oracle**（按需）：作为业务数据源接入，非平台自身运行所必需。Oracle 11g 等低版本需启用 Thick 模式，详见 [architech/design/ORACLE_INTEGRATION_GUIDE.md](architech/design/ORACLE_INTEGRATION_GUIDE.md)。

---

## 3. 部署流程 (Deployment Flow)

### 3.1 第一步：MySQL 数据库结构初始化

平台采用版本化迁移管理（脚本位于 `db-prod/` 目录）。导入方法如下：

1.  **手动创建数据库（可选）**：

    也可跳过此步，导入脚本会在目标库不存在时自动创建。若需手动创建，请使用 `utf8mb4` 字符集：

    ```sql
    CREATE DATABASE IF NOT EXISTS `yunshu_api_data_platform`
      CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
    ```

2.  **执行结构自动初始化（提供以下两种途径）**：

    *   **途径一：使用 Python 工具导入（推荐）**

        需要在本地准备 Python 虚拟环境并安装 `aiomysql` 依赖：

        ```bash
        # 激活 Python 虚拟环境并安装依赖
        python3 -m venv venv
        source venv/bin/activate
        pip install -r requirements.txt

        # 授权并执行
        chmod +x db-prod/apply-sql.sh
        ./db-prod/apply-sql.sh
        ```

        *注：根据交互提示输入 Host、Port、User、Password 及数据库名，输入 `YES` 即可执行。*

    *   **途径二：免 Python 依赖的纯 Shell 脚本导入**

        仅依赖系统已安装的 `mysql` 命令行客户端，具备与 Python 脚本等价的幂等性过滤机制（自动跳过重复建表、重复列等）：

        ```bash
        chmod +x db-prod/apply-sql-native.sh
        ./db-prod/apply-sql-native.sh
        ```

        *注：根据提示输入 Host、Port、User、Password 及数据库名，输入 `YES` 即可。*

3.  **导入默认管理员账号（可选）**：

    首次部署建议导入管理员数据以建立系统初始连接。

    *提示：在第 2 步执行结构初始化时，导入脚本会在迁移完成后**自动询问是否一键导入管理员数据**。若当时已选择导入，此步骤可跳过；若当时跳过，也可随时手动单独导入：*

    *   **使用 Python 工具**：
        ```bash
        ./db-prod/apply-sql.sh db-prod/INIT-USER-ADMIN.sql
        ```
    *   **使用纯 Shell 脚本**：
        ```bash
        ./db-prod/apply-sql-native.sh db-prod/INIT-USER-ADMIN.sql
        ```

详细的库表结构与迁移说明，请参考：[db-prod/README.md](db-prod/README.md)。

---

### 3.2 方案 A：Docker 容器化部署 (推荐)

通过 Docker 容器化可避免环境依赖缺失造成的各种意外错误。

1.  **获取离线镜像包（提供以下两种途径）**：

    *   **途径一：直接下载官方预编译镜像包（推荐，最便捷）**

        前往 [GitHub Releases](https://github.com/RandyChen1985/yunshu-api-data-platform/releases) 页面，下载对应版本及适合服务器 CPU 架构（如 `linux-amd64` / `linux-arm64`）的离线 Docker 镜像 tar 包。

    *   **途径二：本地自行编译并导出镜像包（适合二次开发与定制）**

        执行入口构建脚本时，**必须显式在第一位传入版本号参数**（如 `1.0.0`）：

        ```bash
        cd docker

        # 构建 x86_64 架构 Linux 镜像
        ./build_linux_x86.sh 1.0.0

        # 构建 ARM64 架构 Linux 镜像
        ./build_linux_arm.sh 1.0.0

        # 仅在本机试跑调试（原生架构）
        ./build_native.sh 1.0.0
        ```

        构建完成后，带版本号与平台架构后缀的镜像 tar 归档包将固定生成在 `docker/release/` 目录下（例如 `yunshu-api_1.0.0_linux-amd64_20260628.tar`）。

2.  **载入离线镜像包**：

    将下载或自行编译生成的镜像 tar 包拷贝到目标运行服务器上，执行：

    ```bash
    docker load -i yunshu-api_1.0.0_linux-amd64_20260628.tar
    docker tag yunshu-api:1.0.0 yunshu-api:latest
    ```

3.  **准备容器环境变量配置文件及 Docker Compose 编排调整**：

    *   **配置环境变量**：
        ```bash
        cd docker
        cp ../env.example .env
        # 编辑 .env 文件，填入 MySQL、Redis 及加密密钥等真实配置
        vim .env
        ```
        *注：容器处于网络隔离沙箱中，`MYSQL_HOST` 与 `REDIS_HOST` 严禁配置为 `localhost` 或 `127.0.0.1`，必须设置为宿主机局域网 IP（Mac 上可通过 `ipconfig getifaddr en0` 查询），或使用 `host.docker.internal`。*

        **关键配置项**：
        ```bash
        MYSQL_HOST=192.168.x.x
        MYSQL_DB=yunshu_api_data_platform
        REDIS_HOST=192.168.x.x
        REDIS_ENABLE=true
        ENCRYPTION_KEY=your-fernet-key-here   # API Key 加密密钥，必须配置
        ```

    *   **检查与修改 Docker Compose 编排文件（[docker/docker-compose.api.yml](docker/docker-compose.api.yml)）**：

        1.  **镜像版本校准**：YAML 中默认使用 `image: yunshu-api:latest`。若载入的镜像是带具体版本号的（如 `yunshu-api:1.0.0`），需将 YAML 中 `image:` 指向对应标签；或执行 `docker tag yunshu-api:1.0.0 yunshu-api:latest` 免除修改。
        2.  **Oracle 客户端挂载卷调整（仅当需要直连 Oracle 数据库时）**：根据宿主机 Oracle Instant Client 实际路径，修改 `volumes` 下的挂载目录；若不需要 Oracle，可注释该挂载卷。低版本 Oracle（如 11g）须启用 Thick 模式（`USE_ORACLE_THICK_MODE=1`），详见 [architech/design/ORACLE_INTEGRATION_GUIDE.md](architech/design/ORACLE_INTEGRATION_GUIDE.md)。

4.  **一键启动与停止服务**：

    ```bash
    # 启动 API 容器
    ./start-yunshu-api-server.sh

    # 停止并移除容器
    ./stop-yunshu-api-server.sh
    ```

详细的 Docker 编排配置，请参考：[docker/README.md](docker/README.md)。

---

### 3.3 方案 B：本地源码开发调试部署

适合日常编写业务逻辑、开发调试新功能时采用。

1.  **一键开发启动（推荐）**：

    ```bash
    ./dev.sh
    ```

    脚本会自动清理旧构建、编译前端、释放 8000 端口并在后台启动带 `--reload` 的后端服务，日志输出至 `app.log`。

2.  **分步手动启动**：

    **后端 (FastAPI)**：
    ```bash
    source venv/bin/activate
    pip install -r requirements.txt
    cp env.example .env
    uvicorn app.main:app --reload --port 8000
    ```

    **前端 (Vue 3 + Vite)**：
    ```bash
    cd frontend
    npm install
    npm run dev
    ```

    *注：分步开发时，前端 HMR 与后端 API 分别运行；若只需验证完整打包效果，使用 `./dev.sh` 即可。*

---

## 4. 登录使用 (Getting Started)

服务启动成功后，可通过浏览器访问：

*   **管理后台地址**：`http://localhost:8000/`
*   **Swagger 接口文档**：`http://localhost:8000/docs`
*   **健康检查**：`http://localhost:8000/health`

### 🔑 首次登录指引

1.  管理后台默认采用 **API Key 认证**。
2.  若初始化阶段执行过 `db-prod/INIT-USER-ADMIN.sql`，平台会预置以下默认管理员凭证：
    *   **默认用户名**：`admin`
    *   **默认管理员 API Key**：`YZnxdJLZ0Hwf7IpHXHkYDZYI-CUsTafRjGeANklakuA`
3.  在登录框中粘贴上述 API Key 即可进入管理后台。
4.  若未导入 `INIT-USER-ADMIN.sql`，可在项目根目录执行：
    ```bash
    python3 scripts/create_admin_user.py
    # 或
    python3 scripts/create_admin_key.py
    ```
5.  **安全提示**：默认管理员 API Key 为固定值，首次登录成功后，请尽快在【用户管理】中轮换 API Key 或创建新的管理员账号。

API 调用与认证细节，请参考：[docs/guides/getting-started.md](docs/guides/getting-started.md) · [architech/design/API_INTEGRATION_GUIDE.md](architech/design/API_INTEGRATION_GUIDE.md)。

---

## 5. 相关配置初始化 (Configuration Initialization)

首次成功登录后，建议完成以下核心配置，以保证数据 API 与 SQL 实验室正常工作：

### 5.1 数据源管理 (Data Sources)

*   在【数据源管理】中添加业务数据库连接（支持 MySQL、ClickHouse、Oracle 等）。
*   点击「连通性测试」确认连接无误；Oracle 低版本请参考 [architech/design/ORACLE_INTEGRATION_GUIDE.md](architech/design/ORACLE_INTEGRATION_GUIDE.md) 配置 Thick 模式。

### 5.2 元数据与 API 资源 (Metadata & Resources)

*   在【元数据管理】中维护数据集、表、字段与指标语义。
*   通过 `TABLE` 零代码映射或 `SQL` 自定义逻辑，将资源发布为 `/api/v1` 对外接口，并配置 RBAC 访问权限。

### 5.3 大模型配置（SQL 实验室 AI 辅助，可选）

*   在【系统配置】中配置 OpenAI 兼容的大模型服务（API Base URL、API Key、默认 Model），为 SQL 实验室的智能生成、纠错与对话式分析提供能力。
*   若不使用 AI 辅助功能，可跳过此步，平台核心 Data API 与元数据治理功能不受影响。

### 5.4 SSO 单点登录（可选）

*   若需对接企业统一认证，请在 `.env` 中配置 `SSO_API_URL`、`SSO_ACCESS_TOKEN` 等环境变量。

---

## 6. FAQ (常见问题解答)

### Q1: 运行 `build_linux_arm.sh` 或 `build_linux_x86.sh` 编译前端时报 `Killed / cannot allocate memory` 错误

*   **原因**：在 Mac M 芯片或轻量级虚拟机上，使用 Qemu 模拟异构架构（如 `linux/amd64`）执行 Node.js 的 Vite 生产编译时，容易产生内存溢出 (OOM) 导致进程被系统强杀。
*   **解决**：构建系统已集成 **宿主机预构建机制**。构建异构镜像时，脚本会自动在 macOS 宿主机进行 vite build，跳过容器内模拟编译。请确保宿主机已安装 Node.js（`node` 和 `npm` 可执行）。若仍想在容器内编译，请将 Docker Desktop 可用内存调至 **8GB 或更大**。

### Q2: 容器启动后自动退出，通过 `docker logs` 查看报错数据库连接失败

*   **原因**：`docker/.env` 中 `MYSQL_HOST` 或 `REDIS_HOST` 写了 `localhost` 或 `127.0.0.1`。容器内 `localhost` 指向容器自身，无法访问宿主机上的 MySQL / Redis。
*   **解决**：将 Host 改为宿主机局域网 IP（Mac 上执行 `ipconfig getifaddr en0`）；或在 Mac/Windows Docker Desktop 环境下使用 `host.docker.internal`。

### Q3: 运行表初始化脚本时报错 `ModuleNotFoundError: No module named 'aiomysql'`

*   **原因**：未激活 Python 虚拟环境，或未安装项目依赖。
*   **解决**：先激活虚拟环境（`source venv/bin/activate`），运行 `pip install -r requirements.txt`；或改用免 Python 的 `./db-prod/apply-sql-native.sh`（仅需 `mysql` 客户端）。

### Q4: 数据库迁移报外键错误 3780（列类型/排序规则不兼容）

*   **原因**：MySQL 8.0 对外键列的字符集、排序规则与长度要求严格一致。
*   **解决**：使用项目提供的 `db-prod/apply-sql.sh` 幂等导入（已内置 `utf8mb4_unicode_ci` 对齐）；若手动执行过部分脚本，请检查相关列的 `VARCHAR` 长度与 `COLLATE` 是否与父表一致，参考 `V1-resource-status-mapping.sql`、`V5-alter-resource-key-length.sql`。

### Q5: API Key 登录失败或认证报错

*   **原因**：`.env` 中 `ENCRYPTION_KEY` 未配置，或与创建 API Key 时使用的密钥不一致。
*   **解决**：确认 `ENCRYPTION_KEY` 已正确设置（Fernet 格式）；重新执行 `python3 scripts/create_admin_user.py` 生成新管理员；Docker 部署时确认 `docker-compose.api.yml` 已将 `ENCRYPTION_KEY` 传入容器环境。

### Q6: Mac 上 `docker buildx` 不可用

*   **原因**：Homebrew 安装的 `docker` CLI 配合 Colima 时，可能缺少 buildx 插件。
*   **解决**：在 `docker/` 目录执行 `./install-buildx.sh`，然后重新运行 `./build_linux_x86.sh <version>`。
