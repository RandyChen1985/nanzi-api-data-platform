# Redis 缓存与 Key 设计规范

本系统利用 Redis 作为高性能缓存和并发控制层，涵盖身份认证、权限聚合、Dashboard 统计、动态限流、系统/资源配置、查询结果缓存及调度器分布式锁。

## 1. 缓存设计概览

| 类别 | 核心策略 | 典型 TTL | 一致性保障 |
| :--- | :--- | :--- | :--- |
| **认证与权限** | Read-Through | 1 小时 | 更新用户/角色/Key 时主动失效 |
| **Dashboard 统计** | TTL-Based | 1–5 分钟 | 短 TTL 自然刷新 |
| **动态流控** | Atomic Counter | 60 秒 | 按分钟分片，到期自动清理 |
| **系统配置** | Read-Through | 1 小时 | 修改配置时删除对应 Key |
| **资源元数据** | Read-Through | 1 小时 | 资源 CRUD 时 `invalidate_cache` |
| **业务查询/SQL** | TTL-Based | 动态 (0–3600s+) | 由请求或资源配置控制 |
| **调度器锁** | SET NX EX | 120 秒 | 任务结束或 TTL 到期释放 |

---

## 2. Key 规范与细节

### 2.1 身份认证与权限 (Security)

| Key 规范 | 说明 | 内容结构 | TTL |
| :--- | :--- | :--- | :--- |
| `auth:api_key:{sha256}` | API Key 校验缓存 | user_id, 姓名, 角色, 限流值 | 1h |
| `sys:auth:permissions:v2:user:{uid}` | 聚合权限集 | menus, elements, resources, datasources, data_tables | 1h |

实现：`app/services/auth_service.py`、`app/services/permission_service.py`

### 2.2 Dashboard 统计分析

| Key 规范 | 说明 | TTL |
| :--- | :--- | :--- |
| `dashboard:stats:{role}:{period}` | 总调用量/成功率卡片 | 5m |
| `dashboard:user-stats:{username}:{period}` | 单用户统计 | 5m |
| `dashboard:trends:{role}:{days}` | 多周期趋势折线 | 5m |
| `dashboard:trends24h:{role}` | 24 小时趋势 | 5m |
| `dashboard:peak24h:admin` | 24 小时分时峰值 | 5m |
| `dashboard:resource-stats:{role}:{period}:{limit}` | 接口热度排行 | 2m |
| `dashboard:user-ranking:{period}:{limit}` | 用户活跃排行 | 2m |

> **已废弃**：`dashboard:activities:{role}:{limit}` — 当前代码未使用，请勿在新功能中引用。

实现：`app/api/portal/endpoints/dashboard.py`

### 2.3 动态流控 (Rate Limiting)

| Key 规范 | 说明 | TTL |
| :--- | :--- | :--- |
| `ratelimit:v1:{uid}:{YYYYMMDDHHmm}` | API v1 分钟级计数 | 60s |

逻辑：用户级 → 角色级 → 全局开关（`ratelimit.enabled`）。Redis 不可用时 Fail-Open。

实现：`app/core/dependencies.py`

### 2.4 系统配置

| Key 规范 | 说明 | TTL |
| :--- | :--- | :--- |
| `yunshu:config:{config_key}` | UI 可改的全局配置项 | 1h |

实现：`app/services/system_service.py`

### 2.5 资源元数据配置

| Key 规范 | 说明 | TTL |
| :--- | :--- | :--- |
| `yunshu:meta:config:{resource_key}` | 单资源完整配置（含 cache_ttl 等） | 1h |

实现：`app/services/meta_service.py` — 资源增删改须调用 `MetaService.invalidate_cache`

### 2.6 业务结果缓存

| Key 规范 | 说明 | TTL |
| :--- | :--- | :--- |
| `yunshu:query:{res_key}:{params_hash}` | `/api/v1/query` 查询结果 | 资源 `cache_ttl` |
| `yunshu:sql_exec:{query_hash}` | `/api/v1/sql/execute` 执行结果 | 请求 `cache_ttl` 或系统默认 |

`query_hash` / `params_hash` 均为 MD5，SQL 缓存含数据源 ID、最终 SQL 与 params。

### 2.7 调度器分布式锁

| Key 规范 | 说明 | TTL |
| :--- | :--- | :--- |
| `scheduler:lock:{job_name}` | 多 Worker 下保证单实例执行 | 120s（可配置） |

实现：`app/jobs/scheduler.py` 装饰器 `@with_scheduler_lock`

---

## 3. 运维与开发规范

1. **主动失效**
   - 权限变更：`PermissionService.invalidate_user_cache` / `invalidate_role_cache`
   - 资源变更：`MetaService.invalidate_cache(resource_key)`
   - 系统配置：`system.py` 更新时删除 `yunshu:config:{key}`

2. **安全性**
   - `auth:api_key` 存储 Key 的 **SHA256 哈希**，非明文

3. **序列化**
   - 统计/查询缓存使用 `json.dumps(..., default=str)` 处理 Decimal、DateTime

4. **监控入口**
   - Redis 概览：`GET /api/portal/monitor/redis`（需管理员）
   - 连接池状态：`GET /api/portal/pool/status?source_id={id}`

---

*文档更新日期：2026-06-29*
