> **Project Notice**  
> This is a **personal open-source** project for free learning and exchange, released under the [MIT](LICENSE) License and free to redistribute.  
> The original name “Yunshu” (云枢) conflicted with other enterprise projects, so it has been renamed to “NanZi”.  
> “NanZi” comes from my long-used screen name, echoing the Chinese idiom **孜孜不倦** (diligent and tireless) — a nod to AI that keeps learning and evolving.

# NanZi API Data Platform (NanZi · 数据服务平台)

[简体中文](README.md) | **English**

> **Enterprise-grade Data API & Metadata Governance Platform**  
> *Connect Data. Serve Intelligence.*

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg?logo=python&logoColor=white)](https://www.python.org/) [![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/) [![Vue](https://img.shields.io/badge/Vue-3.x-4FC08D.svg?logo=vue.js&logoColor=white)](https://vuejs.org/) [![TailwindCSS](https://img.shields.io/badge/Tailwind-3.x-38B2AC.svg?logo=tailwind-css&logoColor=white)](https://tailwindcss.com/) [![ClickHouse](https://img.shields.io/badge/ClickHouse-Ready-FFCC00.svg?logo=clickhouse&logoColor=black)](https://clickhouse.com/) [![MySQL](https://img.shields.io/badge/MySQL-8.0-4479A1.svg?logo=mysql&logoColor=white)](https://www.mysql.com/) [![Redis](https://img.shields.io/badge/Redis-Active-DC382D.svg?logo=redis&logoColor=white)](https://redis.io/) [![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

![NanZi API Data Platform Overview](docs/images/overview.png)

**NanZi API Data Platform** is a one-stop **Data-as-a-Service (DaaS)** hub for enterprise data consumption. It wraps physical tables, custom SQL, and semantic metadata into governable, auditable, and observable RESTful APIs — providing standardized data access for AI agents, operations consoles, and business systems.

The platform focuses on the following core capability matrix:

*   🚀 **Resource-as-an-API**: Dual-mode `TABLE` zero-code mapping and `SQL` logic encapsulation; Jinja2 dynamic templates + unified DSL query entry.
*   🧪 **SQL Lab**: Online editing, debugging, AI-assisted SQL generation and repair; one-click publish to production API resources.
*   🗂️ **Metadata & Data Source Governance**: Multi-source connections (MySQL / ClickHouse / Oracle), semantic metadata, health scoring, and fine-grained RBAC.
*   📦 **Data Product Catalog**: Productized API publishing, domain browsing, access request/approval workflow, asset panorama KPIs, and call-volume insights.
*   🛡️ **Enterprise Security & Audit**: Daily-sharded audit logs, AST-based SQL guards, API Key + Session dual auth, data masking policies.
*   📊 **Full-Stack Observability**: 24h/7d call trends, Top rankings, minute-level stats aggregation, connection pool health monitoring.
*   🔌 **Open Integration**: Standardized `/api/v1` public APIs and Portal admin APIs; serves as the data foundation for **[NanZi AI Agent Platform](https://github.com/RandyChen1985/nanzi-ai-agent-platform)**.

---

## 🏛️ Architecture

![NanZi API Data Platform Architecture](docs/images/architech.png)

---

## 🖼️ Interface Snapshots

| 🔐 Login | 📊 Observability Dashboard |
| :---: | :---: |
| ![Login](docs/images/login.png) | ![Dashboard Overview](docs/images/dashboard.png) |
| **🚀 API Resource Management** | **🧪 SQL Lab** |
| ![Resource Management](docs/images/resource.png) | ![SQL Lab](docs/images/sqllab.png) |
| **🛡️ RBAC & Roles** | **📋 Full-Chain Audit Logs** |
| ![RBAC](docs/images/rbac.png) | ![Audit Logs](docs/images/audit.png) |
| **📦 Data Product Catalog** | **🌐 Asset Panorama** |
| ![Data Product Catalog](docs/images/catalog.png) | ![Asset Panorama](docs/images/panorama.png) |

---

## 🌟 Core Capabilities

![NanZi API Data Platform Core Capabilities](docs/images/features.png)

### 1. 🚀 Resource-as-an-API

*   **Dual-mode engine**: `TABLE` mode maps physical tables directly; `SQL` mode encapsulates complex query logic.
*   **Jinja2 dynamic templates**: Inject conditional branches in custom SQL for high-performance parameterized filtering.
*   **Unified query DSL**: `/api/v1/query` and `/api/v1/resources/{key}` support `EQ` / `IN` / `LIKE` / range filters.

### 2. 🧪 AI-Powered SQL Lab

*   **Intelligent SQL assistance**: LLM generation, syntax correction, and Chinese field label completion.
*   **Conversational analytics**: Streaming analysis reports with auto-generated ECharts visualization configs.
*   **One-click publish**: Promote debugged SQL to RBAC-controlled API resources instantly.

### 3. 🗂️ Metadata & Data Source Management

*   **Multi-source connection pools**: Unified management of MySQL, ClickHouse, and Oracle with role isolation.
*   **Semantic metadata**: Structured modeling of datasets, tables, fields, metrics, and entity relationships.
*   **Health governance**: Metadata health scores, creator tracking, and permission simulator.

### 4. 🛡️ Security, Audit & RBAC

*   **Fine-grained RBAC**: Permissions down to data sources, physical tables, API resources, and UI elements.
*   **Full-chain audit**: `api_access_logs_YYYYMMDD` daily sharding for high-volume log read/write.
*   **SQL safety guards**: `sqlparse` static analysis blocks `DELETE`/`DROP` and enforces `LIMIT`.
*   **Data masking**: Global / role / user-level masking strategies with configurable field rules.

### 5. 📊 Observability & Operations

*   **Real-time dashboard**: Call trends, Top APIs/users, online user statistics.
*   **Minute-level aggregation**: `APScheduler` async rollup into `api_access_stats_1m` for fast dashboards.
*   **Connection pool monitoring**: Per-data-source pool activity and health visualization.

### 6. 📦 Data Product Catalog & Asset Panorama

*   **Product publishing**: One-click or batch publish from resource management; full lifecycle from draft → published → offline.
*   **Catalog browsing**: Filter by business domain, call volume, and featured picks; published product metadata visible to all users with clear access status.
*   **Access requests**: Users without permission submit requests from product detail pages; owners/admins approve and resource permissions sync automatically.
*   **Asset panorama**: Domain distribution, zero-call alerts, KPI stats, and call trends (`/api/portal/catalog/panorama`).
*   **Governance tools**: Redundant product detection, CSV export, batch owner assignment, and Playground quick-debug entry points.

---

## 🔄 Typical Data Consumption Flow

1.  **Register data sources**: Configure MySQL / ClickHouse / Oracle connections in the admin console.
2.  **Define resources**: Create `sys_resource_meta` entries via table mapping or SQL Lab.
3.  **Publish to catalog**: Promote API resources as data products with domain, summary, owner, and other metadata.
4.  **Discover & request access**: Users browse and filter the catalog; submit access requests when needed; approved users gain API access.
5.  **External calls**: Clients call `/api/v1/query` or direct resource endpoints with `X-API-Key`.
6.  **Audit & trace**: All calls are logged in daily-sharded tables with Trace ID support.

See [architech/design/API_INTEGRATION_GUIDE.md](architech/design/API_INTEGRATION_GUIDE.md) · [docs/guides/getting-started.md](docs/guides/getting-started.md)

---

## 📚 Documentation

| Doc | Description |
|-----|-------------|
| [HOW_TO_INSTALL.md](HOW_TO_INSTALL.md) | Installation & FAQ |
| [architech/README.md](architech/README.md) | Architecture doc index |
| [architech/design/API_INTEGRATION_GUIDE.md](architech/design/API_INTEGRATION_GUIDE.md) | Public API integration guide |
| [architech/api-schema/sql_execution_api_usage.md](architech/api-schema/sql_execution_api_usage.md) | SQL execution API reference |
| [docs/guides/getting-started.md](docs/guides/getting-started.md) | Developer quick start |
| [architech/design/ORACLE_INTEGRATION_GUIDE.md](architech/design/ORACLE_INTEGRATION_GUIDE.md) | Oracle data source setup |
| [db-prod/README.md](db-prod/README.md) | Database migrations & idempotent apply tools |
| [docker/README.md](docker/README.md) | Docker build & deployment |
| [architech/design/redis_key_design.md](architech/design/redis_key_design.md) | Redis key design |
| [tests/CHECKLIST.md](tests/CHECKLIST.md) | Automated test checklist |

---

## 📂 Project Structure

```text
.
├── app/                  # Backend core (FastAPI)
│   ├── api/              # API layer (v1 public API / portal admin)
│   ├── core/             # Core config (middleware, DB, Redis)
│   ├── services/         # Business logic (metadata, auth, AI, query engine, catalog)
│   │   └── data_adapter/ # Multi-source adapters (MySQL / ClickHouse / Oracle)
│   ├── utils/            # Utilities (shard routing, encryption)
│   └── jobs/             # Scheduled jobs (stats aggregation, log cleanup)
├── frontend/             # Vue 3 admin console (Vite + TailwindCSS)
├── architech/            # Architecture docs & API schema notes
├── db-prod/              # DB migration scripts (V0-VNN) & apply tools
├── docker/               # Container packaging & Docker Compose deployment
├── docs/                 # Integration guides & ops docs
├── scripts/              # Ops helper scripts
├── tests/                # Pytest suites & verification checklist
└── openspec/             # OpenSpec change tracking
```

---

## 🚀 Quick Start

### Requirements

| Component | Version |
|-----------|---------|
| Python | 3.10+ (3.13 recommended) |
| Node.js | 18+ |
| MySQL | 8.0+ |
| Redis | 6.0+ (optional, recommended) |

### 🐳 Docker Deployment (Recommended)

**1. Configure environment**

```bash
cd docker
cp ../env.example .env   # DB, Redis, ENCRYPTION_KEY, etc.
```

**2. Build image and export tar**

| Script | Target |
| :--- | :--- |
| `./build_linux_x86.sh <version>` | x86_64 Linux servers (most common) |
| `./build_linux_arm.sh <version>` | ARM64 Linux (Kunpeng / Ampere, etc.) |
| `./build_native.sh <version>` | Host native arch — local testing only |

```bash
# Production (x86) — also use this on Mac when deploying to x86 servers
./build_linux_x86.sh 1.0.0
```

Artifacts are written to **`docker/release/`**, e.g. `nanzi-api_1.0.0_linux-amd64_20260628.tar`. Offline deployment:

```bash
docker load -i docker/release/nanzi-api_1.0.0_linux-amd64_*.tar
docker tag nanzi-api:1.0.0 nanzi-api:latest
```

> On Apple Silicon Macs deploying to x86 servers, use `build_linux_x86.sh`, not `build_native.sh`.

**If `docker buildx` is unavailable** (common with Homebrew `docker` + Colima):

```bash
./install-buildx.sh
./build_linux_x86.sh 1.0.0
```

See [docker/README.md](docker/README.md) for details.

**3. Start services**

```bash
./start-nanzi-api-server.sh
```

Service listens on **http://localhost:8000** (admin console, `/docs` API reference).

---

### 🛠️ Local Development

#### 1. One-Click Dev (Recommended)

```bash
./dev.sh
```

Automatically detects/installs `uv`, prepares a Python `3.11` `.venv`, and installs `requirements.txt` when needed. It prints a non-sensitive summary of uv, Python, the virtual environment, database, and Redis configuration without printing passwords, then cleans old builds, compiles the frontend, frees the configured port (default `8000`), and starts the backend with `--reload`. Use `./dev.sh -d` for daemon mode; logs go to `app.log`. The default PyPI mirror is Tsinghua and can be overridden with `PYPI_INDEX_URL` or the compatible `PIP_INDEX_URL`.

Check the daemon status with `./dev.sh status` and stop it with `./dev.sh stop`. Both commands use the same `.env` / `API_SERVICE_PORT` as startup and only recognize the Uvicorn process managed by this script; `stop` refuses to touch an unrelated process occupying the port. The existing `./stop-dev.sh` remains as a compatibility wrapper.

#### 2. Step-by-Step Manual Setup

```bash
# 1. Setup Python 3.11 environment
uv python install 3.11
uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python --default-index https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
source .venv/bin/activate
cp env.example .env

# 2. Database init (interactive, idempotent)
./db-prod/apply-sql.sh
# Without Python: ./db-prod/apply-sql-native.sh

# 3. Create admin (if INIT-USER-ADMIN.sql was skipped)
.venv/bin/python scripts/create_admin_user.py

# 4. Build frontend
cd frontend && npm install && npm run build && cd ..

# 5. Start backend
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

#### 3. Split Frontend / Backend Dev

```bash
# Terminal 1: backend
uvicorn app.main:app --reload --port 8000

# Terminal 2: frontend HMR
cd frontend && npm run dev
```

---

## 🔗 NanZi Ecosystem

This platform is the **data service layer** in the NanZi AI stack, complementing the [NanZi AI Agent Platform](https://github.com/RandyChen1985/nanzi-ai-agent-platform):

| Platform | Role |
|----------|------|
| **API Data Platform** (this repo) | Data APIs, metadata governance, SQL Lab, data product catalog, asset panorama, audit & RBAC |
| **AI Agent Platform** | AI chat, agent orchestration, ChatBI, knowledge base, MCP plugins |

---

## 🤝 Contributing

Issues and Pull Requests are welcome.

1. **Branching**: Develop from `main`; feature branches named `feature/your-feature-name`.
2. **Commit messages**: Write in **Chinese**, following [Conventional Commits](https://www.conventionalcommits.org/).
3. **Pull Request**: Use [PULL_REQUEST_TEMPLATE.md](PULL_REQUEST_TEMPLATE.md) when opening a PR.
4. **Testing**: Update [tests/CHECKLIST.md](tests/CHECKLIST.md) when adding features.
5. **DB changes**: Add `V{N}-description.sql` under `db-prod/`; migrations must be idempotent.

---

## 💬 Contact & Community

- **Issues**: Report bugs and feature requests on [GitHub Issues](https://github.com/RandyChen1985/nanzi-api-data-platform/issues).
- **Email**: Reach us via Issue comments.

If you have any questions, feature suggestions, or need further technical updates, please scan the QR code to follow our WeChat Official Account:

<img src="docs/images/weixin.png" alt="WeChat QR Code" width="200" />

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).

---

Copyright © 2025-2026 NanZi API Data Platform Contributors. All Rights Reserved.
