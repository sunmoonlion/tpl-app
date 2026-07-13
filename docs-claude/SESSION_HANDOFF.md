# 会话交接（SESSION HANDOFF）

> 这是 Claude Code 解决"上下文清零"问题的核心文档。
> **每次对话结束前更新，下次对话开始时第一个读。**

---

## 当前状态

**日期**：2026-04-08
**阶段**：基础设施 & Auth 对接完成，开始 Admin 前后端联调

**最后完成的工作**：
- tpl-web-backend（NestJS）启动修复：SWC 路径别名永久修复（tsc-alias），不再需要 runtime bootstrap
- tpl-web-frontend auth 流程打通：登录 → Casdoor OIDC → callback → Redis session → dashboard
- 前端 BFF auth 路由全部删除（`app/api/auth/`），保持前端纯 UI
- Casdoor 官方镜像更新：从旧 Harbor 缓存换成 `casbin/casdoor:latest`，已推 Harbor 并部署
- 顺手清理：`Accept-Language` workaround 从 auth.service.ts 移除（bug 已在新版修复）
- tpl-admin-backend（FastAPI/Python）初步启动：uv 安装 Python，创建 tpl_admin 数据库，修复 alembic 冲突

---

## 下一步要做什么

**下一个任务**：完成 tpl-admin 前后端联调，测试 admin 登录流程

按顺序执行：
1. 等 pnpm install 完成后启动 admin 前端：`pnpm dev --host`（端口 5173）
2. 在 Casdoor 管理后台为 `app-tpl-admin` 应用添加 redirect URI：`http://43.159.148.235:8001/auth/callback`
3. 访问 `http://43.159.148.235:5173` 测试 admin 登录流程
4. admin backend 的 alembic 迁移问题：`command.upgrade` 不能在 async lifespan 里调用，已临时移除，后续需要正确处理（单独 CLI 命令或 asyncio.run 隔离）

---

## 当前进程状态（需要手动重启）

| 服务 | 启动命令 | 端口 |
|------|---------|------|
| tpl-web-backend | `node dist/main`（在 tpl-web-backend/app/） | 8000 |
| tpl-web-frontend | `npm run dev`（在 tpl-web-frontend/app/） | 3000 |
| tpl-admin-backend | `uv run uvicorn app.main:app --host 0.0.0.0 --port 8001`（在 tpl-admin-backend/app/） | 8001 |
| tpl-admin-frontend | `pnpm dev --host`（React 模板，在 tpl-admin-frontend/，需先 pnpm install） | 5173 |

---

## 环境连接参数

| 服务 | 地址 | 认证 |
|------|------|------|
| 服务器外网 IP | `43.159.148.235` | - |
| PostgreSQL（k8s NodePort） | `llmops.sunmoonai.com:30444` | sunmoonai_dev / Po!s1359 |
| Redis（k8s NodePort） | `llmops.sunmoonai.com:30446` | default / Re!d1359admin |
| Casdoor | `https://casdoor.sunmoonai.com` | admin / ? |
| Harbor | `harbor.sunmoonai.com:30443` | admin / Ha!r1359admin |
| k8s 集群 C1 | kubeconfig: `~/.kube/cluster-c1-admin.conf` | SSH: zym@115.190.64.131:1022 |

---

## 关键文件位置

| 路径 | 说明 |
|------|------|
| `tpl-web-backend/app/.env` | 后端环境变量（含 NODE_TLS_REJECT_UNAUTHORIZED=0） |
| `tpl-web-frontend/app/.env.local` | 前端环境变量（NEXT_PUBLIC_API_URL） |
| `tpl-admin-backend/app/.env` | admin 后端（CASDOOR_REDIRECT_URI 已改为外网 IP） |
| `tpl-admin-frontend/.env` | React admin 前端（VITE_API_URL 已改为外网 IP） |
| `~/packages-to-be-installed/images/casdoor-latest.tar` | Casdoor 官方镜像离线备份（64MB） |

---

## 已知问题 / 待处理

| 问题 | 状态 |
|------|------|
| admin backend alembic 迁移不能在 async lifespan 调用 | 临时移除，需后续正确处理 |
| Casdoor admin 密码未知 | 上次尝试 `ChangeMeASAP123!` 失败，剩余尝试次数未知 |
| tpl-admin-frontend pnpm install 可能还在进行 | 完成后需启动 |

---

## 如何快速接续

新对话开始时：
1. 读本文件 → 知道当前状态
2. 检查各服务进程是否还活着（`netstat -ano | grep :8000/:8001/:3000/:5173`）
3. 如进程已死，按上面启动命令重启
4. 继续 admin 联调

---

## 更新记录

| 日期 | 更新内容 |
|------|---------|
| 2026-04-08 | 初始化，记录 auth 对接完成状态和 admin 联调进度 |
