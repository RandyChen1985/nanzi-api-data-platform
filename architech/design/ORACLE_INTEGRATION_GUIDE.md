# Oracle 数据库集成与适配指南 (Oracle Integration Guide)

本指南说明在 FastAPI 异步环境下对接 Oracle（含 11g 等低版本）时的模式选择、连接池初始化与排障要点。

---

## 1. 核心技术选型：Thin vs Thick Mode

`python-oracledb` 提供两种工作模式：

| 特性 | **薄模式 (Thin Mode)** | **厚模式 (Thick Mode)** |
| :--- | :--- | :--- |
| **库依赖** | 纯 Python，无需 Instant Client | **必须安装 Oracle Instant Client** |
| **异步支持** | **原生 `async/await`** | **无原生异步 API** |
| **数据库版本** | 建议 Oracle 12.1+ | **支持 Oracle 11.2+** |
| **并发模型** | 协程非阻塞 | 同步调用需 `asyncio.to_thread` |

> **结论**：目标库为 Oracle 11g 时，设置 `USE_ORACLE_THICK_MODE=1`，使用**同步连接池 + 线程包装**。

---

## 2. 环境配置 (以 Docker 为例)

### 2.1 环境变量与挂载

```yaml
# docker-compose.yml 片段
services:
  api:
    environment:
      - USE_ORACLE_THICK_MODE=1
      - LD_LIBRARY_PATH=/opt/oracle/instantclient
    volumes:
      - /path/to/host/instantclient_19_30:/opt/oracle/instantclient
```

本地开发可参考根目录 `env.example`（默认 `USE_ORACLE_THICK_MODE=0`）与 `docker/env.example`（默认 `1`）。

---

## 3. 项目中的实现位置

### 3.1 初始化入口：`app/services/pool_manager.py`

**不在** `app/main.py` 中重复初始化。`pool_manager` 在模块导入时根据环境变量执行：

```python
# 逻辑摘要 — 见 app/services/pool_manager.py
if os.environ.get("USE_ORACLE_THICK_MODE") == "1":
    oracledb.init_oracle_client(lib_dir=lib_dir)  # 或依赖 LD_LIBRARY_PATH
    pool = oracledb.create_pool(...)              # 同步池
else:
    pool = await oracledb.create_pool_async(...)  # 薄模式异步池
```

`app/main.py` 注释说明：Oracle Thick Mode 已在 `pool_manager` 导入时完成。

### 3.2 适配器：`app/services/data_adapter/oracle.py`

厚模式下通过 `asyncio.to_thread` 包装同步 `pool.acquire()` / `cursor.execute()`，避免阻塞事件循环。

### 3.3 SQL 执行 LIMIT 策略

`/api/v1/sql/execute` 对 Oracle 使用 ROWNUM 子查询包装（见 `sql_execution._enforce_limit`），与 MySQL `LIMIT` 行为对齐。

---

## 4. 规避 DPY-2053（模式冲突）

**原因**：进程内先 `init_oracle_client`（厚模式），再调用 `create_pool_async` 等异步 API。

**修正**：

- 厚模式：仅用 `create_pool` / `connect`
- 薄模式：仅用 `create_pool_async` / `connect_async`
- 全局只初始化一次 `init_oracle_client`

---

## 5. 常见问题排查

### 5.1 DPI-1047: Cannot locate Oracle Client library

- **Linux**：确保 `LD_LIBRARY_PATH` 在进程启动前包含 Instant Client 目录
- 运行 `ldd libclntsh.so` 检查是否缺少 `libaio`

### 5.2 DPY-2053: Thin mode cannot be used because thick mode has already been enabled

- 检查是否混用 `_async` 后缀方法
- 确认仅 `pool_manager.py` 一处初始化

### 5.3 连接测试

管理后台「数据源管理 → 连通性测试」或 API：

- Portal：`POST /api/portal/datasource/test`（见数据源管理模块）
- 连接池健康：`POST /api/portal/pool/health/check`

---

## 6. 项目 Checklist（当前实现状态）

| # | 项 | 状态 | 位置 |
| :--- | :--- | :---: | :--- |
| 1 | `oracledb` 依赖 | ✅ | `requirements.txt` |
| 2 | Thick 模式初始化 | ✅ | `app/services/pool_manager.py`（模块导入） |
| 3 | 同步/异步池分支 | ✅ | `DataSourcePoolManager._create_oracle_pool` |
| 4 | 线程隔离执行 | ✅ | `app/services/data_adapter/oracle.py` |
| 5 | SQL Lab / v1 SQL 限流 | ✅ | `sql_execution._enforce_limit` |
| 6 | 单元测试 | ✅ | `tests/unit/test_oracle_adapter.py`、`test_pool_manager_oracle_dsn.py` |

---

*文档更新日期：2026-06-29*
