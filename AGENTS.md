# 云枢 · 数据服务平台 — Agent 协作指南

## 项目概述

企业级 Data API 与元数据治理平台（FastAPI + Vue 3）。对外 `/api/v1`，管理后台 `/api/portal`。

## 关键目录

| 路径 | 说明 |
|------|------|
| `app/api/v1/` | 对外 Data API |
| `app/api/portal/` | 管理后台 API |
| `app/services/data_adapter/` | MySQL / ClickHouse / Oracle 适配器 |
| `app/jobs/` | 定时任务（聚合、清理），经 Redis 锁防重复 |
| `frontend/src/` | Vue 3 管理后台 |
| `db-prod/` | 数据库迁移 V0–VNN |
| `docker/` | 容器构建与 Compose |
| `tests/` | Pytest 测试 |
| `openspec/` | 接口规范变更 |

## 开发约定

1. **Commit 消息**：中文，Conventional Commits 格式
2. **数据库变更**：在 `db-prod/` 新增幂等 SQL，更新 `tests/CHECKLIST.md`
3. **环境变量**：以 `app/core/config.py` 和 `env.example` 为准
4. **SQL 安全**：只读查询须经 `sqlparse` 校验，参数化绑定
5. **权限**：细粒度 RBAC，Admin 可 bypass

## 常用命令

```bash
./dev.sh                                    # 本地一键启动
uvicorn app.main:app --reload --port 8000   # 仅后端
cd frontend && npm run dev                  # 仅前端热更新
pytest tests/ -v                            # 运行测试
cd docker && ./build_linux_x86.sh 1.0.0     # 构建 x86 镜像
```

## 生产部署要点

- Docker 默认 `gunicorn` + `UvicornWorker`，`WEB_CONCURRENCY=4`
- 定时任务通过 Redis 分布式锁去重，多 Worker 安全
- `ENABLE_SCHEDULER=0` 可关闭调度（独立 scheduler 进程场景）
- 健康检查：`GET /health`（含 MySQL / Redis 探活）

## 禁止事项

- 不要在 Cookie 或日志中存储明文 API Key / 密码
- 不要跳过 SQL 安全校验直接执行用户输入
- 不要提交 `.env` 或真实密钥到仓库
