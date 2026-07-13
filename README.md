# tpl-app


通用应用模板，包含四个可开发子模块和两个配套 Worker 运行角色，用于快速初始化新项目。

模板中的四个组件和两个 Backend 的 DB、S3、Elasticsearch 能力均保持完整。
运行时是否创建 Pod，只在 K8s 部署配置中按集群决定。

<!-- synced with init.sh + web-frontend Next standalone -->

## 仓库结构

```
tpl-app/
├── init.sh                  # 初始化脚本
├── .cursor/rules/           # Cursor 规则（.mdc，按 globs 生效）
├── CLAUDE.md                # AI 协作入口（不保存平行项目事实）
├── docs/                    # 工具无关的当前文档入口
├── docs-worker/             # Worker 使用说明
├── nodebullworker-tpl-web-backend/ # web-backend 的 Bull/Redis Worker 部署
├── celeryworker-tpl-admin-backend/ # admin-backend 的 Celery/RabbitMQ Worker 部署
├── tpl-admin-frontend/      # 管理后台主模板（React 19 + React Router，CSR）
├── tpl-admin-backend/       # 管理后台后端（FastAPI + SQLAlchemy）
├── tpl-web-frontend/        # 用户端前端（Next.js 16，SSR）
└── tpl-web-backend/         # 用户端 BFF 后端（NestJS + TypeScript）
```

## 子模块说明

| 子模块 | 技术栈 | 说明 |
|--------|--------|------|
| tpl-admin-frontend | React 19 + React Router + Vite | 管理后台主模板，CSR 模式 |
| tpl-admin-backend | FastAPI + Python 3.12 | 管理后台后端，DDD 架构，Casdoor BFF 认证 |
| tpl-web-frontend | Next.js 16 + shadcn/ui | 用户端前端，SSR 模式，Casdoor BFF 认证 |
| tpl-web-backend | NestJS + TypeScript | 用户端 BFF 后端，Casdoor OIDC 对接 |

## 组合方式

四个子模块可按需两两组合：

```
管理端：tpl-admin-frontend  +  tpl-admin-backend
用户端：tpl-web-frontend    +  tpl-web-backend
```

两个 Worker 不是新的业务组件或独立数据所有者：

- `celeryworker-tpl-admin-backend` 复用 `tpl-admin-backend` 的镜像、代码、配置和数据责任。
- `nodebullworker-tpl-web-backend` 复用 `tpl-web-backend` 的镜像、代码、配置和数据责任。
- 模板实例化时始终生成两个 Worker；是否在某个集群启动，由 App 的 K8s 聚合部署开关决定。
- Worker 不直接扩大数据库写入边界，仍遵守对应 Backend 的唯一写入和权威读取规则。

详细说明：

- [Celery Worker 使用说明](docs-worker/celery-worker-使用说明.md)
- [Node Bull Worker 使用说明](docs-worker/nodebull-worker-使用说明.md)

BFF 认证说明：
- 当前建议采用「后端 BFF 统一对接 Casdoor」模式：
  - `tpl-web-frontend` 跳转到 `tpl-web-backend /auth/login`
  - `tpl-admin-frontend` 跳转到 `tpl-admin-backend /auth/login`
  - 前端不直接对接 Casdoor token 交换流程

## 当前认证与权限架构（已落地）

本仓库当前以 **Casdoor 为唯一身份源**，目标是：
- 用户注册/创建在 Casdoor 完成
- 登录与会话由后端 BFF 处理
- 接口级权限由 Casdoor token 声明驱动
- 本地用户表仅做影子同步（映射/业务扩展），不是认证权威

### 1) `tpl-web-backend`（NestJS）

已完成：
- `/auth/login|callback|logout|me` Casdoor OIDC 链路
- `JwtGuard` 从 `session_id` 读取 Redis 会话
- `RolePermissionGuard` 改为读取 `req.user.casdoorPermissions`
- `AuthService` 从 `id_token` 解析 claims，并组装 `username` + `casdoorPermissions`
- 登录回调后自动 upsert 本地 `users`（影子同步）
- 禁用手工创建用户：`POST /user` 返回 `410 Gone`
- 去除本地密码认证链路（不再用于本地登录）

说明：
- 权限字符串需要与后端装饰器拼接一致（如 `user:read`）
- 若 token 中给到 `*`，可作为全量放行（仅建议测试/过渡）

### 2) `tpl-admin-backend`（FastAPI）

已完成：
- 仅保留 `/auth/login|callback|logout|me`
- 登录回调后自动解析 `id_token` 并 upsert 本地 `users`（影子同步）
- 字段同步：`username`、`casdoor_sub`、`email`、`full_name`
- 仍由 Casdoor 负责认证与权限权威

### 3) 影子同步原则

影子表用途：
- 业务关联（外键/展示）
- 审计快照
- 本地扩展字段

非用途：
- 不做登录密码校验
- 不作为权限权威（权限以 Casdoor 为准）

### 4) Casdoor 配置要求

必须保证：
- `CASDOOR_REDIRECT_URI` 与后端回调地址完全一致
- token 中可解析出后端需要的权限声明
- 权限命名与后端一致（`resource:action`）

当前后端会从以下 claims 字段提取权限：
- `permissions`
- `permission`
- `roles`
- `role`

### 5) 子模块协作（推送 / 拉取）

**口诀：推送先子后父，拉取先父后子。**

#### 推送建议（先子后父）

无论在父仓库还是任一子仓库里改了代码，若要把结果同步到远程协作，都应：

1. 在**涉及改动的子模块目录**内：`git add` → `git commit` → `git push`（每个动过的子模块各做一遍；若子模块处于 detached HEAD，见下方说明）。
2. 回到**父仓库根目录**（如 `tpl-app`）：`git add` → `git commit` → `git push`，把子模块目录在父仓库里记录的**提交指针**一并推上去。

父仓库只记录各子模块**目录**对应哪一个提交，不会跟踪子模块内部的源码文件。暂存指针时可用 `git add <子模块目录>` 只更新某一个子模块；若图省事、且 `git status` 确认没有误纳入其它改动，也可在父根直接 `git add .`（会同时暂存父仓库自己的文件与已变化的子模块指针）。

**父仓库里 `git add` 举例**（均在父仓库根目录执行）：

| 场景 | 常用命令 |
|------|----------|
| 只把「某子模块」更新后的指针写进父仓库 | `git add tpl-admin-frontend`（目录名即 `.gitmodules` 里的 `path`） |
| 只提交父仓库自己的文件（如改了 `README.md`） | `git add README.md`，或确定没有其它暂存需求时用 `git add .` |
| 既改了 `README.md`，又在子模块里 `push` 了新提交，要一次提交父仓库 | `git add .`（会暂存 `README.md` + 各子模块目录的指针变化） |
| 只想提交父文件、**不要**顺带更新某个子模块指针 | 不要用 `.`，改为 `git add README.md` 等具体路径 |

注意：子模块**内部的**源码改动，只能在**进入该子模块目录后**用 `git add` / `commit`，不要在父仓库里对 `tpl-xxx/src/...` 单独 `add`。

**子模块 detached HEAD 怎么推**

子模块经常会被父仓库检出到某个具体提交，`git status` 可能显示：

```bash
HEAD detached from xxxxxxx
nothing to commit, working tree clean
```

这不是错误。若你已经在该子模块里提交了新 commit，只是当前不在本地 `master` 分支上，不能直接依赖 `git push`。常用做法是明确把当前 HEAD 推到远程 `master`：

```bash
git push origin HEAD:master
```

如果你希望子模块回到本地 `master` 分支再推，也可以先把 `master` 指到当前提交：

```bash
git branch -f master HEAD
git switch master
git push origin master
```

推完子模块后，仍然要回到父仓库根目录提交子模块指针。

**命令示例**（假设父仓库根目录名为 `tpl-app`）：

```bash
# 例 1：只更新「管理端前端」子模块指针（子模块里已 commit + push 完毕）
cd tpl-app
git add tpl-admin-frontend
git commit -m "chore: bump tpl-admin-frontend"
git push origin master

# 例 2：图省事——父仓库里改了 README，且一个或多个子模块指针也变过，一起在父仓库提交
cd tpl-app
git status    # 确认暂存范围
git add .
git commit -m "docs: 更新说明并同步子模块指针"
git push origin master

# 例 3：只提交父仓库文件，不动任何子模块指针（不要用 git add .）
cd tpl-app
git add README.md
git commit -m "docs: 修订 README"
git push origin master
```

#### 状态查看（父仓库 + 所有子模块一次看全）

在父仓库根目录可直接执行（按你使用的终端选择）：

```bash
# PowerShell（Windows，兼容 PowerShell 5）
git status --short; git submodule foreach --recursive "git status --short"

# bash / zsh / Git Bash
git status --short && git submodule foreach --recursive 'git status --short'
```

若你希望长期使用一条短命令，可配置 alias：

```bash
# 仅当前仓库生效（推荐）
git config alias.allstatus '!git status --short; git submodule foreach --recursive "git status --short"'

# 若想全局生效（当前用户所有仓库）
git config --global alias.allstatus '!git status --short; git submodule foreach --recursive "git status --short"'
```

配置后在父仓库根目录执行：

```bash
git allstatus
```

#### 拉取建议（先父后子）

先在本仓库**根目录** `git pull`，拿到父仓库最新提交（含子模块指针变更），再执行子模块初始化/更新，与远程对齐。

**首次克隆**（本地还没有本仓库时，一次拉齐父仓库 + 所有子模块）：

```bash
git clone --recurse-submodules https://gitee.com/sunmoonlion/tpl-app.git
```

**后续更新**（本地已有父仓库，只同步远程最新代码时）：

```bash
cd <父仓库根目录>   # 例如 tpl-app
git pull
git submodule update --init --recursive
```

若出现 `not our ref`，通常是父仓库记录的子模块提交在子仓远程不存在，需要修复子模块指针或恢复对应提交。

### 6) Backend 数据库供给（`db-access-bootstrap` + 各 backend 自带 `db-provisioner`）

当 `tpl-app` 中任一 backend（如 `tpl-admin-backend` / `tpl-web-backend`）需要数据库时，使用：

- 业务侧脚手架：
  - `tpl-admin-backend/db-access-bootstrap/`
  - `tpl-web-backend/db-access-bootstrap/`
- 底层开通能力（**各 backend 目录内各有一份，互不同步；与 `k8s` 仓库解耦**）：
  - `tpl-admin-backend/db-provisioner/bin/dbctl`
  - `tpl-web-backend/db-provisioner/bin/dbctl`

`db-access-bootstrap` 负责组织服务配置和执行流程；同级的 **`db-provisioner`** 负责数据库租户开通/回收与输出适配（k8s Secret / external env）。整仓单独迁出时只需带走对应 backend 下的 **`db-provisioner`** 与 **`db-access-bootstrap`**。

#### 快速上手

```bash
cd tpl-admin-backend/db-access-bootstrap   # 或 tpl-web-backend/db-access-bootstrap
# 1) 按需修改该 backend 的 config/common.env 与 config/*.env
# 2) 推荐一键：provision + 合并 ../app/.env + 生成 .env.reference
./merge-and-generate-app-env.sh external   # 或 k8s / merge-only，详见各 db-access-bootstrap/README.md
# 亦可单独：./setup-external-db-access.sh / ./setup-k8s-db-access.sh
```

示例配置可直接参考：

- `tpl-admin-backend/db-access-bootstrap/config/postgresql.k8s.env`
- `tpl-web-backend/db-access-bootstrap/config/redis.k8s.env`

### 7) Backend 平台数据能力

两个 Backend 默认完整具备数据库、对象存储和 Elasticsearch 接入能力：

- `tpl-admin-backend/storage-access-bootstrap/`
- `tpl-web-backend/storage-access-bootstrap/`

两套脚手架默认启用。它们调用 Data Platform 的统一 Provisioner，根据声明创建
Bucket、最小权限 IAM 身份，并向目标 Namespace 下发独立 ConfigMap 和
Secret；Elasticsearch 脚手架创建独立索引、Alias、角色和访问凭据。

模板不预先永久固化业务职责。具体功能开发时遵守：每类业务数据在任一时刻
只有一个 Backend 写入，并由该 Backend 提供权威读取 API。另一个 Backend
通过 API、事件或任务消息使用该数据。

```bash
cd tpl-web-backend

./storage-access-bootstrap/storage-access-bootstrap.sh validate
./storage-access-bootstrap/storage-access-bootstrap.sh provision
./search-access-bootstrap/search-access-bootstrap.sh provision
```

生成 Backend 的 Kubernetes 部署目录时默认引用 `<backend>-s3` 和
`<backend>-elasticsearch` ConfigMap/Secret：

```bash
./k8s-scaffold/scaffold.sh tpl-web-backend 8000 \
  --type backend
```

Frontend 不得启用该选项或持有长期 S3 凭据。

## 使用方法

### 1. 克隆模板（含子模块）

```bash
git clone --recurse-submodules https://gitee.com/sunmoonlion/tpl-app.git <新项目名>-app
cd <新项目名>-app
```

### 2. 执行初始化脚本

```bash
bash init.sh <项目名> <Gitee用户名>
```

示例：

```bash
bash init.sh investment sunmoonlion
```

脚本会自动完成：
- 将四个子模块和两个 Worker 模板内的 `tpl` / `Tpl` / `TPL` 替换为项目名
- 重命名四个子模块和两个 Worker 目录，并修正各子模块 `.git` 指针
- 更新 `.gitmodules` 中的远程 URL
- 若当前是 Git 克隆：同步父仓 `.git/modules/*`、各子模块的 `worktree` 与远程 URL、父仓 `.git/config` 中的子模块段，并把索引里的子模块路径从 `tpl-*` 改为 `<项目名>-*`（避免仅改目录名后 `git submodule` 断裂）

### 3. 重命名父目录

```bash
cd ..
mv <新项目名>-app <正式目录名>
```

### 4. 在 Gitee 上新建仓库

需要新建五个仓库（均为空仓库，不加 README）：

- `<项目名>-app`
- `<项目名>-admin-frontend`
- `<项目名>-admin-backend`
- `<项目名>-web-frontend`
- `<项目名>-web-backend`

### 5. 推送

```bash
# 推送四个子模块；两个 Worker 由父仓库直接跟踪，不是独立仓库
cd <项目名>-admin-frontend && git push -u origin master && cd ..
cd <项目名>-admin-backend  && git push -u origin master && cd ..
cd <项目名>-web-frontend   && git push -u origin master && cd ..
cd <项目名>-web-backend    && git push -u origin master && cd ..

# 推送父仓库
git remote set-url origin https://gitee.com/<Gitee用户名>/<项目名>-app.git
git push -u origin master
```
