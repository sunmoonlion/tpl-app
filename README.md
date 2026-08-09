# tpl-app

App Platform Architecture v2 的规范应用模板。默认实例固定由两个 Next.js 前端和一个
FastAPI Backend 组成：

```text
tpl-app/
├── tpl-backend/                 # Admin/Web/Internal 共用的领域 Backend
├── tpl-admin-frontend/          # Next.js 管理端
├── tpl-web-frontend/            # Next.js 用户端
└── k8s-scaffold-v2/             # API/Worker/Scheduler/Migration 运行角色生成器
```

## 默认组件

| 组件 | 技术栈 | 职责 |
| --- | --- | --- |
| `tpl-backend` | FastAPI / Python 3.12 | 领域、数据所有权、Admin/Web/Internal API、异步任务 |
| `tpl-admin-frontend` | Next.js / React | 管理和治理表面 |
| `tpl-web-frontend` | Next.js / React | 用户产品表面、SSR/SEO 和交互体验 |

Admin 与 Web 是两个独立浏览器表面，但调用同一个 Backend。Backend 是唯一数据所有者，
前端和 Next.js BFF 不得直接拥有领域数据。

## Backend 运行角色

Worker 仍是生产必需能力，但不再是独立源码工程。`tpl-backend` 的同一个不可变镜像按不同命令
运行：

- API：`uvicorn app.bootstrap.api:app ...`
- Worker：`celery -A app.bootstrap.worker:celery_app worker ...`
- Scheduler：`celery -A app.bootstrap.scheduler:celery_app beat ...`
- Migration：`python -m app.bootstrap.migration`

四个角色使用独立 ServiceAccount、数据库 principal、消息凭据、资源、探针和扩缩容策略。
规范部署声明由 [k8s-scaffold-v2/README.md](k8s-scaffold-v2/README.md) 生成；禁止恢复
`celeryworker-*`、`nodebullworker-*` 或旧 `k8s-scaffold/` 源码副本。

## 参考实现

下列子模块只用于对照或回归，不进入默认实例化链：

- `tpl-admin-frontend-react`：React Router 管理端参考；
- `tpl-admin-frontend-vue`：Vue 管理端参考；
- `tpl-web-backend-nest`：NestJS Backend 参考。

旧 FastAPI `tpl-web-backend` 已在 Architecture v2 配对、迁移和回滚门禁完成后从父仓活动拓扑
解除；远端仓库、冻结提交和历史 release manifest 继续提供审计与恢复能力。

## 初始化新 App

只在新克隆的、可丢弃的模板工作树执行：

```bash
git clone --recurse-submodules --branch architecture-v2 \
  https://github.com/sunmoonlion/tpl-app.git new-app
cd new-app
./init.sh tools sunmoonlion
```

脚本会把三个默认组件改为 `tools-backend`、`tools-admin-frontend`、
`tools-web-frontend`，从实例父仓移除参考子模块，并更新 GitHub 子模块地址。远端目标仓必须在
推送前创建；推送顺序始终是“子仓先推，父仓后提交 gitlink”。

`init.sh` 是一次性、原地转换工具，不得在权威 `tpl-app` 工作树直接执行。公共能力后续变更仍须
先进入模板、通过配对与 K8s 门禁，再同步到实例，不能靠重复运行初始化脚本覆盖领域代码。

## Backend 本地验证

```bash
cd tpl-backend/app
uv sync --frozen
uv run ruff check .
uv run pyright
uv run pytest -q
```

## Kubernetes 模板验证

```bash
python3 -m unittest discover -s k8s-scaffold-v2/tests -v
python3 verify_template_release.py
```

正式部署镜像必须使用 `repository@sha256:...`，不能使用可变 tag。R3/R4 的冻结模板 release
仍由 `template-release-manifest.json` 描述；该文件记录历史验收对象，不随父仓清理而重写。

## 子模块协作

GitHub `origin` 是规范远端，Gitee `gitee` 是镜像远端。修改活动子模块时先在子仓提交和推送，
再回父仓提交 gitlink。更新工作树：

```bash
git pull --ff-only
git submodule sync --recursive
git submodule update --init --recursive
```

架构阶段、镜像晋级和实例同步以 `k8s` 仓库的
`sunmoonai/docs/app-platform-architecture-v2-refactor-plan.md` 为唯一施工基线。
