# 云枢 · 数据服务平台 — 前端

Vue 3 + TypeScript + Vite + TailwindCSS 管理后台。

## 开发

```bash
npm install
npm run dev          # http://localhost:5173，API 代理至 :8000
```

## 脚本

| 命令 | 说明 |
|------|------|
| `npm run dev` | 开发热更新 |
| `npm run build` | 类型检查 + 生产构建 |
| `npm run typecheck` | 仅 TS 类型检查 |
| `npm run lint` | ESLint 检查 |

## 目录结构

```
src/
├── api/          # 按领域封装的 API 模块（auth、metadata 等）
├── components/   # 可复用组件
├── composables/  # 组合式函数
├── router/       # 路由与 RBAC 守卫
├── utils/axios.ts # 统一 axios 实例（API Key、401 处理）
└── views/        # 页面
```

## 环境变量

| 变量 | 说明 |
|------|------|
| `VITE_API_BASE_URL` | 可选，覆盖 API 基址 |
| `VITE_APP_VERSION` | 构建时注入版本号 |

## 与后端联调

- 开发模式：Vite 将 `/api`、`/docs` 代理到 `http://127.0.0.1:8000`
- 生产模式：静态文件由 FastAPI 挂载 `frontend/dist`
