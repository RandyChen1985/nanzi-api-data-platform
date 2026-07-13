# 🎉 Yunshu API Data Platform v1.0.1 Release Notes

Welcome to **v1.0.1** of Yunshu API Data Platform (云枢 · 数据服务平台)! 🚀

**GitHub Repository**: [RandyChen1985/yunshu-api-data-platform](https://github.com/RandyChen1985/yunshu-api-data-platform)

v1.0.1 是 v1.0.0 之后的**首个功能大版本**，在原有 Data API、元数据治理与 SQL 实验室基础上，补齐了企业落地最常见的三块能力：**面向业务用户的数据产品目录**、**面向数据工程师的 SQL Lab 生产力套件**、**面向治理团队的数据源 AI 摸排**。同时新增 **SQL Server** 适配、**MCP Server** 开放接入、**资源配置版本化**与**多渠道变更通知**，显著缩短「建连接 → 理解表 → 写 SQL → 发布 API → 业务消费」的闭环路径。

本次发布范围自 `6ed7790`（含）至 `0c7e57e`（`main`），共 **57 个功能提交**（不含 merge commit），新增数据库迁移 **V26–V39**（14 套脚本），涉及后端 API、Vue 3 管理后台、摸排后台任务与 Docker 构建链路的系统性增强。

---

## 📊 版本概览（v1.0.0 → v1.0.1）

| 维度 | v1.0.0 | v1.0.1 新增/增强 |
| :--- | :--- | :--- |
| **对外入口** | 管理后台 + Data API | **数据产品目录门户**（默认首页） |
| **支持数据源** | MySQL / ClickHouse / Oracle | **+ SQL Server**（ODBC 17/18、TLS 诊断、兼容模式） |
| **SQL Lab** | 基础预览 + AI 生成 | **全栈增强**：多视图结果、分页/EXPLAIN/导出、表探索器、收藏、分析会话 |
| **元数据治理** | 语义建模 V2 | **+ 摸排画像直导**、向量一键同步、健康度优化 |
| **资源治理** | 发布/禁用 | **+ 版本历史/回滚**、批量操作、目录联动 |
| **通知能力** | — | **站内通知** + 钉钉审批 + **企微群** Webhook |
| **开放集成** | REST `/api/v1` | **+ 云枢 MCP Server**（SSE，系统配置开关） |
| **数据库脚本** | V0–V25 | **+ V26–V39** |
| **部署镜像** | 1.0.0 | **1.0.1**（内置 SQL Server ODBC 驱动） |

---

## ✨ 平台能力矩阵（v1.0.1 完整态）

📚 **数据产品目录** · 🧪 **SQL Lab 全栈** · 🔍 **AI 智能摸排** · 🗄️ **SQL Server 多源**  
🔔 **变更通知** · 📜 **配置版本历史** · 🔌 **MCP Server** · 🎨 **品牌个性化**  
📱 **移动端管理台** · 🛡️ **细粒度 RBAC**（延续 v1.0.0）· 📋 **审计与可观测**（延续 v1.0.0）

---

## 🔄 典型业务闭环（本版重点场景）

### 场景 A：数据产品经理发布可发现的数据产品

1. 数据工程师在 **SQL Lab** 调试 SQL 并一键发布为 API 资源。
2. 产品经理在 **数据产品目录** 中将资源包装为「数据产品」（Markdown 说明、领域标签、负责人）。
3. 业务用户在目录门户浏览、申请权限；审批人在 **权限审批** Tab 处理申请。
4. API 配置变更时，负责人收到 **站内通知**；可选推送至钉钉/企微群。
5. 在 **资产全景** 查看产品调用量、热门排行（本版修复统计为 0 的缺陷）。

### 场景 B：新数据源接入后的「AI 摸排 → 元数据 → 取数」

1. DBA 注册 MySQL / Oracle / **SQL Server** 等连接并测试连通性。
2. 在数据源卡片启动 **智能摸排**（串行、可中断、支持全量重跑 `force`）。
3. 在 **摸排资产浏览** 或 SQL Lab **高级模式** 查看表/字段 AI 画像（术语、描述、标签、置信度）。
4. 通过 **智能导入向导** 将摸排画像直导语义元数据，跳过重复 AI 解析。
5. 分析师在 SQL Lab **表探索器** 按标签/收藏/已摸排筛选表，侧栏查看表详情（默认数据预览 + 摸排字段说明），编写分析 SQL。

### 场景 C：分析师自助取数与 AI 洞察

1. 在 SQL Lab **自助取数模式** 执行查询，结果区切换表格/图表/透视/统计/行转列。
2. 固定基准对比两次查询结果；分页浏览大结果集；异步导出最多 5 万行。
3. 打开 **AI 数据专家分析** 弹层：流式洞察、图表建议、引导追问；支持 **中断/复制/重试**。
4. 保存查询模板与分析会话；对 AI 生成 SQL 提交赞/踩反馈供运营复盘。

---

## 🚀 Key Features（详细说明）

### 1. 📚 数据产品目录（Data Product Catalog）

将 API 资源包装为面向业务方的「数据产品」，形成可发现、可申请、可治理的目录门户。

**门户与展示**

* 默认首页切换为 **产品目录**；精选推荐轮播、双列卡片列表、领域统计与搜索。
* 产品详情支持 **Markdown** 渲染；产品名称一键复制；上下架状态可视化。
* 资产全景：总调用量、热门产品、领域分布（修复 v1.0.0 统计恒为 0 的问题）。

**权限申请与审批**

* 用户在产品详情页发起 **权限申请**；「我的申请」Tab 展示状态与统计角标。
* 审批人通过「权限审批」Tab 批量处理；移动端补全相关菜单入口。
* **Breaking**：`menu:catalog:requests` 不再默认授予全部角色，须在角色管理中显式分配 `element:catalog:review` 或对应菜单权限。

**运营与治理**

* 从 API 资源 **批量发布** 为目录产品；批量指定负责人；草稿/冗余产品清理。
* 产品下架前预览 **权限持有人**；支持同步权限或撤销访问。
* 产品绑定的 API 资源变更时，与目录状态、负责人策略联动。

**主要 Portal API（节选）**

| 路径 | 说明 |
| :--- | :--- |
| `GET /api/portal/catalog/products` | 产品列表（分页/筛选） |
| `GET /api/portal/catalog/products/{key}` | 产品详情 |
| `POST /api/portal/catalog/products/publish-from-resource` | 从资源发布产品 |
| `POST /api/portal/catalog/products/{key}/access-request` | 提交权限申请 |
| `GET /api/portal/catalog/products/mine-summary` | 我的申请/审批统计 |

**数据库**：`V26` 产品目录核心表与权限申请；`V27` 收紧默认菜单授权。

---

### 2. 🔔 资源治理、版本历史与变更通知

**配置版本历史（V28）**

* `sys_resource_meta` 每次变更写入 **版本快照**，支持版本列表、Diff 对比与 **一键回滚**。
* 资源编辑页可查看「配置变更记录」，目录产品负责人可感知 API 变更。

**变更通知（V29–V30）**

* API 资源配置变更时，向数据产品 **负责人** 写入站内通知。
* 系统配置整合 **钉钉审批推送** Webhook；支持测试连通性与表单校验修复。
* **企业微信群机器人** 通知（V34），适用于运维群广播变更。

**批量与联动**

* 资源列表支持批量上架/禁用；与目录产品发布/删除状态联动，避免「API 已下线但目录仍展示」的不一致。

---

### 3. 🗄️ SQL Server 数据源适配

补齐国内企业最常见的 OLTP 源之一，与现有 MySQL / Oracle / ClickHouse 适配器并列。

**连接与诊断**

* 新增 `sqlserver` 数据源类型；表单支持主机、库名、**高级 ODBC 连接串参数**。
* **未保存配置也可测试连接**（编辑页即时验证）。
* TLS/证书错误友好诊断；Driver 17/18 兼容；**2012/2014 兼容模式**开关。
* 默认对 Driver 18 **关闭 Encrypt**，兼容旧版 TLS 环境。

**运行与部署**

* Docker 镜像内置 **Microsoft ODBC Driver for SQL Server**，支持 `aioodbc` 异步访问。
* 摸排 DDL 查询修复：`:name` 命名参数自动转为 pyodbc `?` 占位符（`82a62ad`）。

**测试**：`tests/unit/test_sqlserver_adapter.py` 覆盖参数绑定与连接串构建。

---

### 4. 🔍 数据源智能摸排（DB Profiling）

对数据源下所有表/视图进行结构采样 + LLM 分析，生成可复用的「表画像草稿库」，**不直接写入正式元数据表**，便于人工筛选后再导入。

**任务模型（V36）**

* 表 `db_profile_tasks`：单数据源 **同一时间仅一个任务**（`uk_conn_task`）；状态排队/进行中/完成/异常。
* 前端高频轮询 `GET .../profile-task` 展示进度条与当前处理表名。
* 支持 **中断**（当前表完成后停止）与 **全量重跑**（`force=true`，覆盖已有画像）。

**画像内容（`db_table_profiles`）**

* 表级：`ai_term`、`ai_description`、`ai_tags`、`confidence_score`、`ddl`、`sample_data`。
* 字段级：`columns_profile` JSON（`name` / `term` / `desc`）。
* 支持标记 **忽略表**（`is_ignored`）、识别临时表（`is_temporary`）。

**前端入口**

* 数据源列表：启动/停止摸排、进度展示、**查看画像**（browse 模式表探索器）。
* SQL Lab 高级模式：侧栏展示摸排术语/描述/置信度；无摸排数据时隐藏「探索/高级」入口。
* 元数据 **智能导入向导**：选择「从摸排画像加载」，跳过 AI 重算。

**画像浏览 API**

| 路径 | 说明 |
| :--- | :--- |
| `GET .../table-profiles/search` | 分页搜索（关键词/标签/已摸排范围） |
| `GET .../table-profiles/tags` | 聚合 AI 标签 |
| `GET .../table-profiles/{table}` | 单表完整画像（含字段画像） |
| `PUT .../table-profiles/ignore` | 手动忽略/启用表 |

> **v1.0.1 修复**：`/search`、`/tags` 路由须注册在 `/table-profiles/{table_name}` **之前**，避免被误匹配为表名导致 404。

**Oracle 专项**：修复 LOB 长连接断连；优化大批量摸排中断与吞吐。

---

### 5. 🧪 SQL Lab 全栈增强

本版对 SQL Lab 的投入最大（20+ 提交），目标是从「能跑 SQL」升级为「能探索、能分析、能协作」的自助取数工作台。

#### 5.1 查询执行与结果分析

* **预览行数可选**（50/100/500 等），支持 `offset` + `include_total` 分页。
* 结果区 **多视图**：表格（虚拟滚动）、纯文本、快速图表、透视、列统计、行转列。
* 列筛选、列复制、JSON 单元格展开；**固定基准**对比两次结果差异。
* `POST /api/portal/lab/explain` 执行计划；`POST /api/portal/lab/check-risks` 高风险 SQL 二次确认。
* **同步导出 Excel**（预览行）+ **异步全量导出**（`lab_export_jobs`，最多 5 万行）。

#### 5.2 表探索器（Table Explorer）

* 弹层式探索：关键词搜索表名/术语/描述/标签；范围切换 **全部表 / 已摸排 / 我的收藏 / 最近使用**。
* 标签侧栏聚合；多选表同步到侧栏勾选；已选表筛选器。
* 行内 **预览数据**（`SELECT *` 限 10 行）；AI 描述完整展示（取消单行截断）。
* Portal API：`GET /api/portal/lab/table-search`、`GET /api/portal/lab/table-tags`。

#### 5.3 侧栏表详情（眼睛图标）

* 打开后 **默认「数据预览」Tab**，并行加载表结构与预览数据。
* 预览区复用 `LabResultDataView`：**与执行结果相同的工具栏**（筛选、多视图、分页、导出 Excel、异步导出、AI 分析、固定基准）。
* **表结构 Tab** 优先展示摸排画像：表级术语/描述/标签/置信度；字段级业务术语与 AI 描述（无摸排时回退库注释）。

#### 5.4 库表收藏与查询历史（V39）

* 表 `lab_table_favorites`：每用户每数据源 **收藏 / 置顶 / 个人备注**，云端同步。
* API：`GET/PUT/DELETE /api/portal/lab/table-favorites`。
* 查询历史支持 **一键清空**（localStorage）。

#### 5.5 保存查询与分析会话（V37）

* `lab_saved_queries`：命名保存 SQL、测试参数、lab 模式、可选团队共享。
* `lab_analysis_sessions`：AI 分析对话存档，支持历史会话面板加载/删除。
* API：`/api/portal/lab/saved-queries`、`/api/portal/lab/analysis-sessions`。

#### 5.6 AI 交互增强

* `POST /api/portal/lab/ai/chat-analysis` **流式**返回；前端支持 **中断生成**（AbortController）。
* 消息下方展示 **时间 / 复制 / 重试**；修复「思考中」重复空白气泡。
* `POST /api/portal/lab/ai/generate-from-profile`：基于摸排画像生成分析 SQL。
* AI 反馈（V38）：`lab_ai_feedback` + 管理端反馈看板；生成 SQL 后快捷赞/踩。
* Markdown 渲染增强：SQL 代码块语法高亮、一键复制；图表 JSON 块自动渲染 ECharts。

#### 5.7 组件架构

* 新增 `LabResultDataView.vue`，由 `ResultPanel` 与表详情预览 **共用**，避免结果展示逻辑分叉。

---

### 6. 🔌 云枢 MCP Server

* 系统配置页管理 MCP **开关**、接入说明与 **公网 Base URL**（V31–V32）。
* 启用后对外提供 SSE 形态的 MCP 服务，供 Cursor / Claude Desktop 等工具发现平台 Data API 能力。
* 与 [云枢 · 智能体平台](https://github.com/RandyChen1985/yunshu-ai-agent-platform) 形成「Agent 编排 + 数据底座」组合。

---

### 7. 🎨 品牌个性化与登录体验

* 系统配置支持自定义 **登录页品牌图、标题、版权信息**（V33、V35）。
* 适用于私有化部署时的企业 Logo 与版权声明替换，无需改代码重新构建前端。

---

### 8. 📱 管理后台体验与元数据增强

* **移动端适配**：目录、审批、数据源等关键页在手机浏览器下可用。
* 搜索框 **一键清空**；下拉操作菜单 `Teleport` 修复（避免被父级 `overflow` 裁剪）。
* 资源编辑 **离开未保存确认**；元数据中心 **待同步数据集一键向量同步**。
* 资源管理列表/侧栏/日志抽屉重构；滚动条悬停导致 **全局页面抖动** 修复。

---

### 9. 👥 角色权限与业务角色 UX

* 业务角色管理：权限树交互优化、成员分配与缓存刷新修复。
* 「我的权限」合并 **配置变更提醒**；产品详情页支持快捷跳转编辑 API 资源。

---

## ⚠️ Upgrade Notes（从 v1.0.0 升级）

> 从 v1.0.0 升级至 v1.0.1 时，请特别注意以下事项：

| 项目 | 说明 |
| :--- | :--- |
| **数据库迁移** | 须执行 **V26–V39** 增量脚本（幂等可重复）；已执行 V0–V25 的环境只需补跑新脚本。 |
| **Docker 镜像** | 请重新构建/拉取 **1.0.1** 镜像；含 SQL Server ODBC 驱动，旧 1.0.0 镜像无法连接 SQL Server。 |
| **摸排与 AI** | 摸排依赖系统 AI 模型配置；首次全量摸排 Token 消耗较大，建议先小库验证。 |
| **调度器** | 多 Worker 部署时摸排任务经 Redis 锁防重复；可用 `ENABLE_SCHEDULER=0` 关闭 Web 内调度改独立进程。 |
| **目录审批权限** | 升级后普通用户默认 **看不到** 审批菜单，需管理员在角色中分配。 |
| **前端缓存** | 升级后务必 **强刷浏览器**（Cmd+Shift+R），避免旧 JS 调用新 API 报 404。 |
| **路由顺序** | 若自行 backport 后端，务必保证 `table-profiles/search` 在 `{table_name}` 之前注册。 |

```bash
# 1. 备份数据库（生产必做）
mysqldump -u... -p... yunshu > backup_pre_1.0.1.sql

# 2. 拉取代码并增量迁移
git fetch && git checkout main && git pull
./db-prod/apply-sql-native.sh

# 3. 重新构建并替换容器
cd docker && ./build_linux_x86.sh 1.0.1
docker load -i release/yunshu-api_1.0.1_linux-amd64_*.tar
docker tag yunshu-api:1.0.1 yunshu-api:latest
./start-yunshu-api-server.sh
```

---

## 🗄️ Database Schema（V26–V39 详细说明）

| 脚本 | 核心表/变更 | 业务含义 |
| :--- | :--- | :--- |
| **V26** | `catalog_products`、`catalog_access_requests` 等 | 数据产品目录、权限申请、UI 权限、负责人策略、种子数据 |
| **V27** | UI 权限调整 | 撤销权限申请菜单默认全员授予 |
| **V28** | `sys_resource_meta_versions` | 资源配置版本快照、对比与回滚 |
| **V29** | `catalog_change_notifications` | 目录/API 变更站内通知 |
| **V30** | 系统配置项 | 钉钉审批 Webhook |
| **V31–V32** | 系统配置项 | MCP Server 开关、公网 Base URL |
| **V33、V35** | 系统配置项 | 品牌图、标题、版权文案 |
| **V34** | 系统配置项 | 企业微信群机器人 Webhook |
| **V36** | `db_profile_tasks`、`db_table_profiles` | 摸排任务与表画像草稿库 |
| **V37** | `lab_saved_queries`、`lab_export_jobs`、`lab_ai_feedback`、`lab_analysis_sessions` | SQL Lab 保存/导出/反馈/会话 |
| **V38** | UI 权限 | AI 反馈管理相关元素权限 |
| **V39** | `lab_table_favorites` | 用户级表收藏/置顶/备注 |

> [!WARNING]
> V26 脚本合并了原分拆迁移（V26–V31 逻辑），新环境一次性执行即可；若曾分项执行过旧脚本，幂等语句可安全跳过。

---

## 📦 Quick Start

部署基础流程与 v1.0.0 相同，详见 [HOW_TO_INSTALL.md](https://github.com/RandyChen1985/yunshu-api-data-platform/blob/main/HOW_TO_INSTALL.md)。

### 本地开发（v1.0.1）

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp env.example .env
./db-prod/apply-sql-native.sh   # 新环境全量；旧环境 V26–V39 增量
./dev.sh
```

### Docker 离线部署（1.0.1）

```bash
cd docker
cp ../env.example .env
./build_linux_x86.sh 1.0.1
docker load -i release/yunshu-api_1.0.1_linux-amd64_*.tar
docker tag yunshu-api:1.0.1 yunshu-api:latest
./start-yunshu-api-server.sh
```

### 🐳 离线环境加载镜像

```bash
docker load -i yunshu-api_1.0.1_linux-amd64_*.tar
docker images | grep yunshu-api
cd docker && ./start-yunshu-api-server.sh
```

---

## ✅ Test Checklist

### v1.0.0 回归（确保无破坏）

- [ ] `/api/v1/resources/{key}` 与 `/api/v1/query` 鉴权、过滤、分页正常。
- [ ] MySQL / ClickHouse / Oracle 连接与预览正常。
- [ ] RBAC、审计日志、可观测看板正常。

### v1.0.1 新增重点

- [ ] **目录门户**：浏览、搜索、申请权限、审批通过/拒绝、上下架。
- [ ] **资产全景**：总调用量、热门产品非 0（有调用数据时）。
- [ ] **资源版本**：修改 SQL 资源后产生版本记录，回滚生效。
- [ ] **变更通知**：修改资源后负责人收到站内信；钉钉/企微 Webhook（如配置）。
- [ ] **SQL Server**：连接测试、Lab 预览、摸排 DDL 与画像生成。
- [ ] **摸排任务**：启动 → 进度轮询 → 中断/完成；全量重跑 `force`。
- [ ] **画像浏览**：数据源「查看画像」列表非空（已摸排库）；点击表可看字段画像。
- [ ] **SQL Lab 表探索器**：搜索/标签/收藏；侧栏眼睛图标默认数据预览 + 工具栏。
- [ ] **SQL Lab 结果**：多视图切换、分页、EXPLAIN、同步/异步导出。
- [ ] **AI 分析**：流式输出、中断按钮、复制/重试、历史会话保存。
- [ ] **表收藏**：收藏/置顶/备注刷新后仍保留。
- [ ] **MCP**：系统配置开启后 SSE 端点可访问（如启用）。
- [ ] **移动端**：目录与审批页手机浏览器布局可用。
- [ ] **pytest**：`pytest tests/ -v` 通过。

完整清单见 [tests/CHECKLIST.md](https://github.com/RandyChen1985/yunshu-api-data-platform/blob/main/tests/CHECKLIST.md)。

---

## 🐛 重要修复摘录

| 问题 | 修复 |
| :--- | :--- |
| 资产全景调用量恒为 0 | 统计 SQL 与资源 Key 关联修正 |
| 摸排浏览 404 `Table profile not found` | FastAPI 路由注册顺序 |
| SQL Server 摸排 DDL 参数错误 | `:name` → pyodbc `?` 转换 |
| Oracle 摸排 LOB 断连 | 连接与读取生命周期优化 |
| 全局页面滚动条抖动 | 滚动条 gutter 稳定化 |
| AI 分析双空气泡 | 合并加载态到占位消息 |
| 目录审批菜单全员可见 | V27 撤销默认授权 + 前端门控 |

---

## 💾 Downloads / Assets

* 📦 **Source Code (zip)**: `yunshu-api-data-platform-1.0.1.zip`
* 📦 **Source Code (tar.gz)**: `yunshu-api-data-platform-1.0.1.tar.gz`
* 🐳 **Docker Image for Linux amd64 (x86_64)**: `yunshu-api_1.0.1_linux-amd64_*.tar`
* 🐳 **Docker Image for Linux arm64 (aarch64)**: `yunshu-api_1.0.1_linux-arm64_*.tar`
* ⚙️ **Docker Compose YAML file**: `docker-compose.yml`

🔗 **下载地址**: [GitHub Releases v1.0.1](https://github.com/RandyChen1985/yunshu-api-data-platform/releases/tag/1.0.1)

---

## 📋 Commit Log

发布基线：`6ed7790` → 发布 HEAD：`0c7e57e`（merge dev @ `70d3e7a`）

<details>
<summary>点击展开全部 57 条提交</summary>

| Hash | 描述 |
| :--- | :--- |
| `70d3e7a` | feat(sqllab): 表详情预览增强、摸排资产浏览与 AI 分析交互优化 |
| `82a62ad` | fix(sqlserver): 摸排 DDL 查询支持 :name 参数转 pyodbc 占位符 |
| `1661d13` | feat(sqllab): 表探索器支持行内数据预览与描述完整展示 |
| `a2303cb` | feat(sqllab): 表探索器与侧栏已选筛选，无摸排时隐藏探索/高级入口 |
| `bb94080` | feat(sqllab): 库表收藏云端同步与侧栏/结果区交互优化 |
| `ebf8fc3` | feat(sqllab): 查询历史支持一键清空 |
| `876c371` | feat(sqllab): SQL Lab P0 能力补全与 AI 分析弹层修复 |
| `f99f459` | feat(sqllab): AI 反馈管理与 AI 分析 Markdown 渲染增强 |
| `d41b603` | feat(sqllab): AI 反馈优化、SQL 自动格式化与 JOIN 交互修复 |
| `b8808f0` | feat(sqllab): SQL Lab 体验增强（结果分析/编辑器/AI/发布闭环） |
| `eff9f4a` | feat(sqllab): SQL Lab 全栈增强（导出/分页/EXPLAIN/保存查询等） |
| `b662970` | feat(sqllab): 预览行数可选与结果多视图展示 |
| `7b025f0` | feat(sqllab): 优化实验室交互与 AI 推荐弹窗布局 |
| `c93470d` | feat(datasource): 数据源侧查看授权与画像弹窗体验优化 |
| `479b88a` | feat(frontend): 搜索框可清空与操作菜单 Teleport 修复 |
| `80c72d8` | feat: 摸排画像直导元数据并完善任务状态同步 |
| `d0cab3f` | feat(profiling): 新增摸排全量重跑按钮与 force 参数 |
| `2a48b5f` | fix(profiling): 修复 Oracle LOB 断连并优化摸排中断与大批量性能 |
| `88d71ae` | feat(sqllab): 优化 AI 交互体验并默认开启高级模式 |
| `bf4fc90` | feat(sqllab): SQL Lab 高级模式支持摸排画像浏览与 AI 分析 |
| `8d18e66` | feat: 数据源摸排功能与 UI 交互全面优化 |
| `a46ee94` | feat(datasource): SQL Server 2014/2012 兼容模式 |
| `62967e0` | fix(datasource): SQL Server TLS 错误诊断与 ODBC 17 兼容支持 |
| `7f1ff83` | feat(datasource): 支持未保存配置的连接测试 |
| `d4cf1c3` | feat(datasource): SQL Server 高级连接参数配置与编辑页测试 |
| `e263f63` | fix(sqlserver): 默认关闭 ODBC Driver 18 加密以兼容旧版 TLS |
| `25224e4` | fix(docker): 镜像安装 SQL Server ODBC 驱动以支持 aioodbc |
| `4d39392` | feat(catalog): 完善资源批量操作与上架禁用联动 |
| `927126e` | feat(catalog): 资源目录发布与删除联动优化 |
| `28ccc0f` | feat(notify): 企微群通知与品牌登录页优化 |
| `b4e0a0b` | feat(branding): 新增品牌版权个性化配置 |
| `513b3bc` | feat(datasource): 新增 SQL Server 数据源适配与 Mock 测试 |
| `117c384` | feat(mcp): 落地云枢 MCP Server 与系统配置管理 |
| `dba8503` | feat(roles): 业务角色管理 UX 优化与权限配置修复 |
| `759a2ba` | feat(catalog): 配置变更提醒并入我的权限，产品详情支持快捷编辑 API |
| `a87f488` | fix(catalog): 优化钉钉测试与通知配置表单禁用逻辑 |
| `3fd5176` | feat(catalog): 目录变更站内通知、钉钉审批推送与系统配置整合 |
| `8228b40` | feat(resource): 资源配置版本历史、回滚与目录配置变更查看 |
| `ff769bd` | feat(frontend): 默认首页改为产品目录并优化导航入口 |
| `5d6f8b6` | style(catalog): 隐藏精选轮播原生滚动条 |
| `7baffa5` | feat(catalog): 目录体验增强—Markdown、精选轮播、上下架与可复制名称 |
| `6c62ad8` | docs: 更新 README 补充数据产品目录与资产全景说明 |
| `5766cfb` | feat(catalog): 我的申请 Tab 统计与目录页体验优化 |
| `0c94f3d` | feat(catalog): 权限审批 Tab 统计与移动端菜单补全 |
| `8b3ae66` | feat(frontend): 管理后台移动端适配与体验优化 |
| `9d16f86` | style(catalog): 产品列表改为双列卡片布局 |
| `eb85b77` | style(catalog): 优化精选推荐卡片与列表风格统一 |
| `546a3b0` | feat(catalog): 我的申请、冗余产品清理与权限同步刷新 |
| `dae2873` | fix(catalog): 修复资产全景总调用量与热门产品统计为 0 |
| `4490439` | fix(catalog): 撤销权限申请菜单默认全员授予并收紧前端门控 |
| `509daa4` | fix(frontend): 目录相关页面去掉 max-width 限制与数据源管理布局一致 |
| `d9260e6` | fix(frontend): 修复滚动条悬停导致的全局页面抖动 |
| `75fbaa4` | feat: 数据产品目录完整模块与品牌图标更新 |
| `1f256c1` | fix(frontend): 修复空 Toast 并限制系统元数据检索资源操作 |
| `927d363` | feat: 元数据中心支持待同步数据集一键向量同步 |
| `5d2a623` | feat: 优化数据源/元数据中心 UX 并修复资源编辑离开确认 |
| `234ef25` | feat: 资源管理体验优化与元数据增强 |

</details>

---

## 🤝 Contributors

感谢所有参与 v1.0.1 版本发布的开发者！

For complete test coverage check out [tests/CHECKLIST.md](https://github.com/RandyChen1985/yunshu-api-data-platform/blob/main/tests/CHECKLIST.md).
