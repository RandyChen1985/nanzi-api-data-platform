# 架构与设计文档

本目录存放云枢·数据服务平台的技术设计说明，与代码实现保持同步。

## 文档索引

| 文档 | 说明 |
| :--- | :--- |
| [design/API_INTEGRATION_GUIDE.md](design/API_INTEGRATION_GUIDE.md) | 对外 `/api/v1` 集成指南（认证、Query、SQL、元数据检索） |
| [api-schema/sql_execution_api_usage.md](api-schema/sql_execution_api_usage.md) | `POST /api/v1/sql/execute` 专项说明 |
| [design/redis_key_design.md](design/redis_key_design.md) | Redis Key 命名、TTL 与失效策略 |
| [design/ORACLE_INTEGRATION_GUIDE.md](design/ORACLE_INTEGRATION_GUIDE.md) | Oracle Thin/Thick 模式与 Docker 配置 |

## 对外 API 速览

| 方法 | 路径 | 权限要点 |
| :--- | :--- | :--- |
| POST | `/api/v1/query` | 资源 Key RBAC |
| GET | `/api/v1/resources/{key}` | 资源 Key RBAC |
| POST | `/api/v1/sql/execute` | `system.sql.execute` + ds/table |
| POST | `/api/v1/meta/search` | `system.metadata.search` |

Portal 管理接口前缀：`/api/portal`（需登录，不在公开 OpenAPI 中）。
