# API 集成指南 (Integration Guide)

本文档面向开发者，介绍如何集成云枢·数据服务平台对外 API（`/api/v1`）。管理后台 Portal API（`/api/portal`）不在 OpenAPI 中公开，需登录控制台使用。

---

## 1. 快速接入

### 1.1 基本信息

| 项 | 值 |
| :--- | :--- |
| **Base URL** | `/api/v1` |
| **协议** | HTTP/1.1（生产环境推荐 HTTPS） |
| **数据格式** | JSON |

### 1.2 认证机制 (Authentication)

平台支持以下凭证（按优先级尝试）：

1. **`X-API-Key` Header**（推荐，对外集成首选）
2. **`Authorization: Bearer <token>` Header**
3. **`admin_token` Cookie**（仅 Portal 浏览器会话，对外集成勿用）

**请求示例:**

```http
GET /api/v1/resources/vm_stats HTTP/1.1
Host: your-api-host.example.com
X-API-Key: YOUR_API_KEY_HERE
Content-Type: application/json
```

或使用 Bearer：

```http
POST /api/v1/query HTTP/1.1
Authorization: Bearer YOUR_API_KEY_HERE
Content-Type: application/json
```

> [!IMPORTANT]
> API Key 是身份凭证，请妥善保管，切勿在前端 JS 中硬编码。建议由后端服务代发请求。

---

## 2. 响应规范

所有 API 返回统一的 JSON 结构。

### 成功响应 (200 OK)

```json
{
  "code": 200,
  "message": "success",
  "data": { "...": "..." },
  "timestamp": "2024-03-20T10:00:00+08:00",
  "trace_id": "a1b2c3d4-e5f6-7890-a1b2-c3d4e5f67890"
}
```

### 错误响应

非 200 时 body 仍为 JSON：

```json
{
  "code": 4011,
  "message": "API Key 缺失",
  "data": null,
  "timestamp": "...",
  "trace_id": "..."
}
```

---

## 3. 核心接口详解

### 3.1 通用逻辑查询 (`POST /query`)

通过 JSON 配置复杂筛选逻辑。

```http
POST /api/v1/query
```

| 字段 | 类型 | 必填 | 说明 |
| :--- | :--- | :--- | :--- |
| `resource` | string | 是 | 资源 Key（需 RBAC 授权） |
| `filters` | array | 否 | `[[字段, 操作符, 值], ...]` |
| `page` | int | 否 | 页码，默认 1 |
| `size` | int | 否 | 每页条数，默认 20，最大 1000 |
| `sort_by` | string | 否 | 排序字段 |
| `sort_order` | string | 否 | `asc` 或 `desc` |

**操作符**：`=`、`!=`、`>`、`>=`、`<`、`<=`、`LIKE`、`IN`

**示例**：

```json
{
  "resource": "host_metrics",
  "filters": [
    ["cpu_usage", ">", 80],
    ["status", "=", "WARNING"]
  ],
  "sort_by": "created_at",
  "sort_order": "desc",
  "page": 1,
  "size": 10
}
```

查询结果可按资源元数据 `cache_ttl` 缓存（Key：`yunshu:query:{resource}:{hash}`）。

### 3.2 资源快捷查询 (`GET /resources/{key}`)

适用于简单等值查询：

```http
GET /api/v1/resources/users?role=admin&page=1&size=20
```

同一参数多次出现（如 `?status=active&status=pending`）会自动转为 `IN` 查询。

### 3.3 动态 SQL 执行 (`POST /sql/execute`)

**高级接口**：需资源权限 `system.sql.execute`，非管理员还需数据源/表级 RBAC。

```http
POST /api/v1/sql/execute
```

| 字段 | 类型 | 必填 | 说明 |
| :--- | :--- | :--- | :--- |
| `data_source` | string/int | 是 | 数据源名称或 ID |
| `sql` | string | 是 | 只读 SQL（SELECT / WITH / SHOW / DESCRIBE / EXPLAIN） |
| `params` | object | 否 | 参数绑定 |
| `cache_ttl` | int | 否 | 缓存秒数；`null`=系统默认，`0`=禁用 |

**安全限制**：

- 禁止 DML/DDL
- 自动 `LIMIT 1000`（Oracle 使用 ROWNUM 包装）
- 响应头 `X-Cache: HIT|MISS` 标识缓存

详细说明见 [SQL 执行 API 使用指南](../api-schema/sql_execution_api_usage.md)。

**示例**：

```json
{
  "data_source": "clickhouse_prod",
  "sql": "SELECT count(*) AS total, status FROM host_metrics WHERE time > %(start_time)s GROUP BY status",
  "params": { "start_time": "2024-01-01 00:00:00" },
  "cache_ttl": 60
}
```

### 3.4 元数据语义检索 (`POST /meta/search`)

面向 AI Agent / 数据分析助手，返回装配后的 YAML 上下文。

```http
POST /api/v1/meta/search
```

**权限**：资源权限 `system.metadata.search`

| 字段 | 类型 | 必填 | 说明 |
| :--- | :--- | :--- | :--- |
| `query` | string | 是 | 关键词或自然语言问题 |
| `data_source` | string | 否 | 数据源编码，默认 `default` |
| `search_type` | string | 否 | `keyword`（模糊匹配）或 `semantic`（向量检索） |
| `enable_rerank` | bool | 否 | 语义检索时是否 Rerank，默认 `false` |

**响应**：

```json
{
  "data": "---\n# 装配后的 YAML 片段...\n",
  "count": 2,
  "dataset_ids": [101, 102]
}
```

- `keyword`：数据库模糊匹配表/指标
- `semantic`：向量库召回，优先使用 Redis 中缓存的 YAML 片段

---

## 4. 最佳实践

### 4.1 错误处理

1. **HTTP Status**：
   - `2xx`：解析 `data`
   - `4xx`：客户端错误，**勿盲目重试**
   - `5xx`：服务端错误，可指数退避重试

2. **记录 `trace_id`**：排障时提供给运维/开发

### 4.2 性能优化

- 控制 `size`，避免单次拉取过大
- 筛选条件尽量命中索引字段
- SQL 接口合理使用 `cache_ttl`
- 元数据检索优先 `keyword`，复杂语义再用 `semantic`

---

## 5. 错误码字典

业务 `code` 定义见 `app/core/errors.py`。

| HTTP 状态 | 业务 Code | 含义 | 处理建议 |
| :--- | :--- | :--- | :--- |
| 400 | 400 | 错误的请求 | 检查请求格式 |
| 400 | 4001 | 无效的参数 | 修正字段类型或必填项 |
| 400 | 4004 | 资源未找到 | 检查 `resource` / 数据源名称 |
| 400 | 4005 | 资源已禁用 | 联系管理员启用资源 |
| 401 | 401 | 未授权 | 检查认证 Header |
| 401 | 4011 | API Key 缺失 | 添加 `X-API-Key` 或 Bearer |
| 401 | 4012 | API Key 无效 | 检查 Key 是否过期/禁用 |
| 401 | 4013 | Token 已过期 | 重新获取凭证 |
| 403 | 403 | 禁止访问 | 检查 RBAC |
| 403 | 4031 | 访问被拒绝 | 申请目标资源/数据源权限 |
| 403 | 4032 | 需要管理员权限 | 使用管理员凭证或申请权限 |
| 429 | 429 | 请求过于频繁 | 降低 QPS 或申请更高配额 |
| 500 | 500 | 服务器内部错误 | 携带 trace_id 联系支持 |
| 500 | 5001 | 数据库错误 | 检查 SQL 或数据源状态 |
| 500 | 5002 | ClickHouse 错误 | 字段/类型不匹配等 |
| 503 | 503 | 服务不可用 | 稍后重试 |
| 503 | 5031 | 数据库连接失败 | 检查数据源连通性 |

---

## 6. 相关文档

| 文档 | 说明 |
| :--- | :--- |
| [SQL 执行 API](../api-schema/sql_execution_api_usage.md) | SQL Lab 对外执行细节 |
| [Redis Key 设计](redis_key_design.md) | 缓存 Key 与失效策略 |
| [Oracle 集成指南](ORACLE_INTEGRATION_GUIDE.md) | Oracle 数据源 Thick 模式 |

---

*文档更新日期：2026-06-29*
