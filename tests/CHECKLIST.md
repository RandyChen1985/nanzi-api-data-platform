# API 自动化测试清单 (API Testing Checklist)

该清单用于追踪各接口的自动化测试覆盖情况及验证状态。

## 1. 动态资源访问 (Dynamic Resource Access)

| 接口路径                                  | 测试用例文件                 | 核心场景验证                                 | 状态   | 最近测试日期 |
| :---------------------------------------- | :--------------------------- | :------------------------------------------- | :----- | :----------- |
| `/api/v1/resources/{key}`                 | `test_universal_resource.py` | 动态适配、分页查询、多维过滤、排序、鉴权隔离 | ✅ 通过 | 2026-01-27   |
| `/api/v1/resources/donghuan_real_metrics` | `test_universal_resource.py` | 适配动环实时指标表，验证字段展示与过滤       | ✅ 通过 | 2026-01-27   |
| `/api/v1/resources/donghuan_events`       | `test_universal_resource.py` | 适配动环事件表，验证复杂字段结构             | ✅ 通过 | 2026-01-27   |
| `/api/v1/resources/yunshu_rooms`          | `test_universal_resource.py` | 适配机房列表，验证基础过滤逻辑               | ✅ 通过 | 2026-01-27   |

## 2. 权限与授权 (Permissions & Auth)

| 接口路径 / 功能            | 测试用例文件         | 核心场景验证               | 状态   | 最近测试日期 |
| :------------------------- | :------------------- | :------------------------- | :----- | :----------- |
| `/api/v1/permission/check` | `test_permission.py` | 资源权限校验、角色权限验证 (修复角色继承漏洞) | ✅ 通过 | 2026-01-28   |

## 3. 管理接口 (Admin APIs)

| 接口路径 | 测试用例文件   | 核心场景验证       | 状态   | 最近测试日期 |
| :------- | :------------- | :----------------- | :----- | :----------- |
| `/keys`  | `test_keys.py` | 密钥创建、重复处理 | ✅ 通过 | 2026-01-27   |

## 4. 通用查询与执行接口 (Query & Execution APIs)

| 接口路径              | 测试用例文件            | 核心场景验证                                 | 状态   | 最近测试日期 |
| :-------------------- | :---------------------- | :------------------------------------------- | :----- | :----------- |
| `/query`              | `test_query.py`         | 动态查询、字段过滤、安全校验                 | ✅ 通过 | 2026-01-27   |
| `/api/v1/sql/execute` | `test_sql_execution.py`, `test_sql_granular_permission.py` | SQL 语句执行、参数化查询、安全限制、**数据源与表级细粒度鉴权** | ✅ 通过 | 2026-01-30   |

## 5. 管理后台接口 (Admin Portal APIs)

| 接口路径                  | 测试用例文件             | 核心场景验证                             | 状态   | 最近测试日期 |
| :------------------------ | :----------------------- | :--------------------------------------- | :----- | :----------- |
| `/api/portal/auth`        | `test_auth.py`           | 登录验证、当前用户信息获取、权限校验 (修复角色继承) | ✅ 通过 | 2026-01-28   |
| `/api/portal/management`  | `test_management.py`     | 用户管理 (CRUD)、状态控制、权限分级      | ✅ 通过 | 2026-01-28   |
| `/api/portal/dashboard`   | `test_dashboard.py`      | 统计数据获取、趋势分析、最近活动、**在线用户详情 (Admin Only)** | ✅ 通过 | 2026-01-30   |
| `/api/portal/audit`       | `test_audit_enhanced.py` | 增强审计日志、高级过滤、导出功能         | ✅ 通过 | 2026-01-28   |
| `/api/portal/logs/access` | `test_access_logs.py`    | 接口访问日志查询、普通用户权限过滤       | ✅ 通过 | 2026-02-02   |
| `/api/portal/system`      | `test_system.py`         | 连接诊断接口、管理员权限校验、组件测试   | ✅ 通过 | 2026-01-28   |
| `/api/portal/monitor`     | (Manual/UI Test)         | 系统资源监控 (CPU/内存/磁盘/Redis)       | ✅ 通过 | 2026-01-28   |
| `/api/portal/user/keys`   | `test_user_api_key.py`   | 个人 API Key 管理、创建、删除、权限绑定  | ✅ 通过 | 2026-01-28   |
| `/api/portal/lab/preview` | `test_lab_security.py`   | SQL Lab 安全拦截、关键字过滤、注释防绕过、**支持 Oracle 数据源预览** | ✅ 通过 | 2026-03-06   |
| `/api/portal/lab/ai/*`    | `test_permission_system.py` | SQL 生成/校验/修改 (已验证角色权限继承) | ✅ 通过 | 2026-01-28   |
| `/api/portal/management/roles/{id}/users` | `test_management_enhanced.py` | **角色成员批量分配、全量覆盖逻辑、缓存失效验证** | ✅ 通过 | 2026-03-13   |
| `/api/portal/meta/*`      | `test_permission_system.py` | 数据源表结构元数据获取 (已验证角色权限) | ✅ 通过 | 2026-01-28   |
| `/api/portal/datasource/*`| `test_datasource_sort.py`, `test_datasource_sqlserver.py` | **数据源 CRUD、排序、SQL Server 类型与连接测试（Mock）** | ✅ 通过 | 2026-07-01   |
| `/api/portal/meta/v2/*`   | `test_meta_v2.py`           | **语义化元数据管理 (V2) CRUD (修复指标/关系编辑按钮缺失)、AI 智能发现指标、YAML 生成、血缘分析、导入表名过滤** | ✅ 通过 | 2026-03-17   |
| `/api/portal/meta/resources/{key}/versions` | `test_resource_versions.py` | **资源配置版本历史、差异对比、回滚** | ✅ 通过 | 2026-07-01   |
| `/api/portal/datasource/datasources/{id}/profile` 等 | (Manual/UI Test) | **数据源智能摸排分析 (Table Profiling)、异步串行采样与 LLM 画像生成、忽略特定资产** | ⏳ 待验 | 2026-07-11   |

## 9. 数据产品目录 (Data Product Catalog)

| 接口路径 | 测试用例文件 | 核心场景验证 | 状态 | 最近测试日期 |
| :------- | :----------- | :----------- | :--- | :----------- |
| `/api/portal/catalog/products` | `test_catalog.py` | 产品列表、域筛选、权限状态、调用量聚合、分页 | ✅ 通过 | 2026-06-29 |
| `/api/portal/catalog/products/{key}` | `test_catalog.py` | 产品详情、字段说明、调用趋势 | ✅ 通过 | 2026-06-29 |
| `/api/portal/catalog/panorama` | `test_catalog.py` | 资产全景 KPI、域分布、零调用告警、调用量统计 | ✅ 通过 | 2026-06-29 |
| `/api/portal/catalog/products/publish-from-resource` | `test_catalog.py` | 从资源发布到目录、发布前校验 | ✅ 通过 | 2026-06-29 |
| `/api/portal/catalog/products/batch-publish` | `test_catalog.py` | 批量上架、跳过不合规草稿并返回报告 | ✅ 通过 | 2026-06-29 |
| `/api/portal/catalog/products/{key}/edit-meta` | `test_catalog.py` | 产品编辑元数据、负责人/数据集下拉 | ✅ 通过 | 2026-06-29 |
| `/api/portal/catalog/access-requests` | `test_catalog.py` | 权限申请列表、审批筛选 | ✅ 通过 | 2026-06-29 |
| `/api/portal/catalog/access-requests/status-counts` | `test_catalog.py` | 审批页各状态 Tab 数量统计 | ✅ 通过 | 2026-06-29 |
| `/api/portal/catalog/access-requests/mine` | `test_catalog.py` | 当前用户提交的申请列表 | ✅ 通过 | 2026-06-29 |
| `/api/portal/catalog/access-requests/mine/status-counts` | `test_catalog.py` | 我的申请页各状态 Tab 数量统计 | ✅ 通过 | 2026-06-29 |
| `/api/portal/catalog/products/mine-summary` | `test_catalog.py` | 我的产品汇总、待审批数 | ✅ 通过 | 2026-06-29 |
| `/api/portal/catalog/products/export` | `test_catalog.py` | 已发布产品 CSV 导出 | ✅ 通过 | 2026-06-29 |
| `/api/portal/catalog/products?only_no_access` | `test_catalog.py` | 无权限产品筛选 | ✅ 通过 | 2026-06-29 |
| `/api/portal/catalog/products/batch-assign-owner` | `test_catalog.py` | 批量指定负责人 | ✅ 通过 | 2026-06-29 |
| `/api/portal/catalog/products/redundant` | `test_catalog.py` | 冗余产品检测（API 合并后） | ✅ 通过 | 2026-06-29 |
| `/api/portal/catalog/products/{key}/resource-conflicts` | `test_catalog.py` | 编辑页关联 API 冲突检测 | ✅ 通过 | 2026-06-29 |
| `/api/portal/catalog/products/{key}/resources` | `test_catalog.py` | 多 API 关联更新 | ✅ 通过 | 2026-06-29 |
| `/api/portal/catalog/products/{key}/sync-access` | `test_catalog.py` | 审批通过后补写资源权限、刷新缓存 | ✅ 通过 | 2026-06-29 |
| `/api/portal/catalog/products/{key}/linked-resource-versions` | `test_catalog.py` | 产品编辑页关联 API 最近版本与变更摘要 | ✅ 通过 | 2026-07-01 |
| `/api/portal/catalog/change-notifications` | `test_catalog_change_notifications.py` | 资源变更通知产品负责人、未读计数与已读 | ✅ 通过 | 2026-07-01 |
| `/api/portal/system/platform-settings` | `test_platform_settings.py` | 系统配置（目录/钉钉/MCP）、MCP 连通性测试 | ✅ 通过 | 2026-07-01 |
| `/api/v1/resources` | `test_resources_list.py` | 可访问资源列表（MCP/Agent 发现） | ✅ 通过 | 2026-07-01 |
| `/api/v1/mcp/status` | `test_resources_list.py` | MCP 启用状态探针 | ✅ 通过 | 2026-07-01 |
| `yunshu_mcp` (stdio/SSE) | 手动 | MCP Server 工具与系统配置开关 | ⏳ 待验 | 2026-07-01 |
| `/api/portal/catalog/settings` | `test_catalog.py` | 负责人策略配置读写 | ✅ 通过 | 2026-06-29 |
| `db-prod/V26-data-product-catalog-module.sql` | 手动 | 数据产品目录全模块 DDL（含权限申请、collation、配置种子） | ⏳ 待验 | 2026-06-29 |
| `db-prod/V27-revoke-catalog-requests-menu-default-grant.sql` | 手动 | 撤销 menu:catalog:requests 全员默认授予 | ⏳ 待验 | 2026-06-29 |
| `db-prod/V28-resource-version-history.sql` | `test_resource_versions.py` | 资源配置版本历史表与回滚能力 | ✅ 通过 | 2026-07-01 |
| `db-prod/V29-catalog-change-notifications.sql` | `test_catalog_change_notifications.py` | 目录/API 变更站内通知与 Webhook 配置 | ✅ 通过 | 2026-07-01 |
| `db-prod/V30-dingtalk-approval-notify.sql` | `test_platform_settings.py` | 钉钉审批通知配置项 | ✅ 通过 | 2026-07-01 |
| `db-prod/V31-mcp-server-config.sql` | `test_resources_list.py` | MCP Server 开关与 instructions 配置 | ⏳ 待验 | 2026-07-01 |
| `db-prod/V33-branding-config.sql` | `test_branding_settings_service.py`, `test_platform_settings.py` | 品牌版权个性化配置与公开接口 | ⏳ 待验 | 2026-07-01 |
| `db-prod/V34-wecom-notify.sql` | `test_wecom_notification_service.py`, `test_platform_settings.py` | 企微群机器人审批通知 | ⏳ 待验 | 2026-07-01 |
| `db-prod/V35-branding-copyright.sql` | `test_branding_settings_service.py` | 登录页底部版权文案配置 | ⏳ 待验 | 2026-07-01 |
| `db-prod/V36-add-datasource-profiling.sql` | 手动 | 数据源摸排任务表 `db_profile_tasks` 与表画像草稿表 `db_table_profiles` | ⏳ 待验 | 2026-07-11 |

| `/api/portal/system/logs` | `test_system_logs.py`    | 系统配置日志、维护日志查询              | ✅ 通过 | 2026-01-27   |

## 6. 系统核心功能 (System Core)

| 功能模块                | 测试用例文件                 | 核心场景验证                                             | 状态   | 最近测试日期 |
| :---------------------- | :--------------------------- | :------------------------------------------------------- | :----- | :----------- |
| API 访问日志 (MySQL)    | `test_logging.py`            | 异步写入 (BackgroundTask)、Trace ID、Body 记录、错误解析 | ✅ 通过 | 2026-02-02   |
| 数据适配器 (ClickHouse) | `test_clickhouse_adapter.py` | SQL 参数化、安全加固、AST 校验、Redis 缓存               | ✅ 通过 | 2026-01-27   |
| 错误处理机制            | `test_error_handling.py`     | 统一异常捕获、HTTP 状态码转换、JSON 响应格式             | ✅ 通过 | 2026-01-27   |
| 元数据 V2 服务逻辑      | `test_metadata_v2_service.py`| **数据集/表/字段/指标/关系 CRUD 及同步逻辑、血缘探测 SQL 生成** | ✅ 通过 | 2026-02-03   |
| 元数据创建人追踪        | `test_metadata_v2_service.py`| **验证数据集、表、指标和关系的创建人 ID 保存及姓名关联查询逻辑** | ✅ 通过 | 2026-03-13   |

## 7. 性能与优化 (Performance & Optimization)

| 优化项             | 验证方式             | 核心场景验证                                              | 状态   | 最近测试日期 |
| :----------------- | :------------------- | :-------------------------------------------------------- | :----- | :----------- |
| Dashboard 缓存     | 接口响应头 `X-Cache` | Redis 缓存命中、TTL 有效性、多维度数据聚合性能            | ✅ 通过 | 2026-01-27   |
| 向量化同步与检索 | `tests/scripts/test_vector_sync.py` | 细粒度(表/指标)向量化存储、Redis索引创建、语义搜索准确性验证 | ✅ 通过 | 2026-02-03   |

## 3. 性能测试 (Performance)
| 日志异步并发安全   | 手动/压力测试        | 确保 Middleware 日志写入不覆盖接口自定义 BackgroundTasks  | ✅ 通过 | 2026-01-27   |
| 大数据量分页 (5M+) | SQL 索引优化 (建议)  | 验证 (user_name, created_at) 联合索引对排序分页的加速效果 | ⏳ 待验 | 2026-01-23   |

## 8. 部署与环境 (Deployment & Environment)

| 验证项          | 验证方式          | 核心场景验证                                     | 状态   | 最近测试日期 |
| :-------------- | :---------------- | :----------------------------------------------- | :----- | :----------- |
| Docker 镜像构建 | `docker/build_linux_x86.sh` | 基础镜像兼容性、Python 依赖冲突 (bcrypt/passlib) | ✅ 通过 | 2026-01-01   |
| 跨平台兼容性    | CI/Docker         | Linux/Slim 镜像下的加密库依赖验证                | ✅ 通过 | 2026-01-01   |

---
**说明**:
- ✅ **通过**: 自动化测试已覆盖并成功运行。
- ⚠️ **警告**: 测试已覆盖但存在部分失败。
- ❌ **未覆盖**: 尚未编写自动化测试。
