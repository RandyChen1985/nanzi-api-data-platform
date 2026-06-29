# SQL 执行 API 使用指南

## 概述

`POST /api/v1/sql/execute` 用于执行动态 SQL 查询，面向只读分析场景。接口提供 API Key / Bearer 认证、资源权限校验、数据源/表级细粒度授权、SQL 安全审计、结果自动限流、可选 Redis 缓存及异步审计日志。

> 更完整的对外集成说明见 [API 集成指南](../design/API_INTEGRATION_GUIDE.md)。

## API 端点信息

| 项 | 值 |
| :--- | :--- |
| **路径** | `POST /api/v1/sql/execute` |
| **认证** | `X-API-Key` 或 `Authorization: Bearer <token>`（见集成指南） |
| **基础权限** | 资源权限 `system.sql.execute`（管理员可绕过） |
| **细粒度权限** | 非管理员还需 `ds:{数据源名}` 及 `ds:{数据源名}:table:{表名}` 或 `ds:{数据源名}:table:*` |
| **限流** | 受系统/角色/用户级分钟限流控制（`429`） |

## 请求结构

### 请求体参数

| 参数名 | 类型 | 必需 | 描述 |
|--------|------|------|------|
| `data_source` | int 或 string | 是 | 目标数据源的 ID 或名称 |
| `sql` | string | 是 | 原始 SQL（仅允许只读语句，见下文） |
| `params` | object | 否 | 参数化查询绑定变量 |
| `cache_ttl` | int | 否 | 缓存 TTL（秒）。`null` = 使用系统默认（通常 30s）；`0` = 禁用缓存 |

### 允许的 SQL 类型

基于 AST 解析（`sqlparse`），**仅允许**以下语句前缀：

- `SELECT`
- `WITH`（CTE）
- `SHOW`
- `DESCRIBE` / `DESC`
- `EXPLAIN`

**禁止** `INSERT`、`UPDATE`、`DELETE`、`DROP`、`ALTER`、`TRUNCATE`、`CREATE`、`GRANT`、`REVOKE` 等变更类语句。

### 自动结果限制

- MySQL / ClickHouse：未指定 `LIMIT` 时自动追加 `LIMIT 1000`
- Oracle：未指定 `FETCH FIRST` / `ROWNUM` 时包装为 `SELECT * FROM (...) WHERE ROWNUM <= 1000`

## 响应结构

### 成功响应 (HTTP 200)

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "columns": [
      { "name": "id", "type": "Int64" },
      { "name": "name", "type": "String" }
    ],
    "items": [
      [1, "alice"],
      [2, "bob"]
    ]
  }
}
```

响应 Header：

| Header | 含义 |
| :--- | :--- |
| `X-Cache: HIT` | 命中 Redis 缓存 |
| `X-Cache: MISS` | 未命中，已查库 |

### 错误响应

| HTTP 状态 | 典型原因 |
|--------|------|
| 400 | SQL 安全校验失败、语法错误或数据库执行异常 |
| 401 | 缺少或无效的 API Key / Token |
| 403 | 缺少 `system.sql.execute`、数据源或表级权限 |
| 404 | 指定的数据源不存在 |
| 429 | 触发分钟级限流 |

## 使用示例

### 示例 1：基本查询（数据源 ID）

```bash
curl -X POST 'https://your-host/api/v1/sql/execute' \
  -H 'X-API-Key: YOUR_KEY' \
  -H 'Content-Type: application/json' \
  -d '{
    "data_source": 1,
    "sql": "SELECT id, name, email FROM users WHERE age > 25"
  }'
```

### 示例 2：使用数据源名称 + 禁用缓存

```json
{
  "data_source": "clickhouse_prod",
  "sql": "SELECT * FROM events WHERE created_at > '2024-01-01'",
  "cache_ttl": 0
}
```

### 示例 3：参数化查询

```json
{
  "data_source": 2,
  "sql": "SELECT * FROM orders WHERE user_id = %(user_id)s AND status = %(status)s",
  "params": {
    "user_id": 123,
    "status": "active"
  }
}
```

### 示例 4：WITH 子查询

```json
{
  "data_source": "analytics_db",
  "sql": "WITH recent AS (SELECT * FROM orders WHERE created_at > '2024-01-01') SELECT COUNT(*) FROM recent"
}
```

## 权限模型（非管理员）

1. **资源权限**：角色须分配 `system.sql.execute`
2. **数据源权限**：须拥有 `ds:{source_name}`（RBAC 数据源授权）
3. **表权限**：
   - `ds:{source_name}:table:*` → 该数据源下所有表
   - `ds:{source_name}:table:{table}` → 白名单表
   - 白名单为空且无 `table:*` → 拒绝任何表访问

SQL 中解析出的表名会与白名单比对（支持 `db.table` 后缀匹配）。

## 缓存机制

- **Key 格式**：`yunshu:sql_exec:{md5}`（由数据源 ID + 最终 SQL + params 计算）
- **默认 TTL**：请求未传 `cache_ttl` 时，读取 `system.sql.execute` 资源配置中的 `cache_ttl`，缺省 30 秒
- **禁用**：`cache_ttl: 0`

详见 [Redis Key 设计规范](../design/redis_key_design.md)。

## 安全与审计

1. **SQL 注入防护**：AST 级只读校验 + 参数绑定
2. **结果保护**：强制上限 1000 行（Oracle 使用 ROWNUM 包装）
3. **审计日志**：异步写入 `sys_api_audit_log`，记录用户、数据源、SQL、耗时、状态（含 `SUCCESS (CACHE)` / `SECURITY_VIOLATION`）

## 调用流程

1. 认证（API Key / Bearer）
2. 限流检查
3. 校验 `system.sql.execute`
4. 解析数据源 → 细粒度 ds / table 权限
5. SQL 安全校验
6. 自动 LIMIT / ROWNUM
7. 读 Redis 缓存（若启用）
8. 适配器执行查询
9. 写缓存 + 返回结果
10. 后台写审计日志

## 适用场景

- 复杂 JOIN / 子查询分析
- SQL Lab 对外程序化调用
- 临时数据提取与验证
- 报表引擎直连查询

---

*文档更新日期：2026-06-29*
