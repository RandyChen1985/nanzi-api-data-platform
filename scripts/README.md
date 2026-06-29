# 运维脚本索引

## 用户与权限

| 脚本 | 说明 |
|------|------|
| `create_admin_user.py` | 创建管理员账号 |
| `create_admin_key.py` | 为已有用户生成 API Key |
| `create_key.py` | 通用 Key 生成 |
| `seed_roles.py` | 初始化 RBAC 角色 |
| `reset_and_init_users.py` | 重置并初始化用户（开发用） |

## 数据与统计

| 脚本 | 说明 |
|------|------|
| `backfill_stats.py` | 回填访问统计聚合数据 |
| `reset_redis_index.py` | 清理 Redis 索引 |

## 部署辅助

| 脚本 | 说明 |
|------|------|
| `wait-for-services.sh` | 等待 MySQL / Redis 就绪 |
| `export_postman.py` | 导出 Postman Collection |
| `run_init_sql.py` | 执行初始化 SQL |

## 开发调试（勿用于生产镜像）

| 脚本 | 说明 |
|------|------|
| `debug_ck_sync.py` | ClickHouse 同步调试 |
| `debug_ck_auth.py` | ClickHouse 认证调试 |
| `debug_ds.py` | 数据源连接调试 |

## 示例

| 脚本 | 说明 |
|------|------|
| `examples/api_client_example.py` | API 调用示例 |
