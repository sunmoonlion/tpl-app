# Architecture v2 模板镜像构建规则

默认发布单元只有三个镜像：`tpl-backend`、`tpl-admin-frontend`、`tpl-web-frontend`。
API、Worker、Scheduler 与 Migration 共用同一个 Backend 镜像，不得分别构建 Worker 镜像。

## 不可变性

- 候选 tag 使用 `arch-v2-<stage>-<git-sha>`；
- K8s release 必须锁定 Harbor 返回的 `repository@sha256:...`；
- 正式 `2.0.0` 只能对已经验收的相同 digest 晋级，禁止重新构建；
- `1.0.0` 是旧架构保护版本，禁止覆盖；
- 构建代理只允许进入 build stage，运行镜像不得保留代理变量。

## Backend

```bash
cd tpl-backend
docker build --progress=plain -f mybuild/Dockerfile \
  --build-arg PYPI_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
  -t harbor.sunmoonai.com:30443/app-images/tpl-backend:arch-v2-<stage>-<git-sha> .
```

同一摘要的运行入口由 K8s 模板决定：

```text
api       uvicorn app.bootstrap.api:app ...
worker    celery -A app.bootstrap.worker:celery_app worker ...
scheduler celery -A app.bootstrap.scheduler:celery_app beat ...
migration python -m app.bootstrap.migration
```

## Admin Next.js

```bash
cd tpl-admin-frontend
docker build --progress=plain -f mybuild/Dockerfile \
  -t harbor.sunmoonai.com:30443/app-images/tpl-admin-frontend:arch-v2-<stage>-<git-sha> .
```

## Web Next.js

```bash
cd tpl-web-frontend
docker build --progress=plain -f mybuild/Dockerfile \
  -t harbor.sunmoonai.com:30443/app-images/tpl-web-frontend:arch-v2-<stage>-<git-sha> .
```

两个前端均使用 Next.js standalone 运行镜像；浏览器 `/api` 由同源入口转发到统一 Backend，
SSR 使用 `BACKEND_INTERNAL_URL` 调用同一 ClusterIP Service。

## 发布前检查

1. 三个源码工作树干净且 commit 已推送；
2. Backend Ruff、Pyright、pytest 通过；
3. 两个前端 typecheck、lint、test、build 通过；
4. 镜像 revision label 等于源码 commit；
5. 远端 digest 已重新读取并写入 scaffold 输入；
6. `python3 verify_template_release.py` 通过；
7. K8s Migration、API、Worker、Scheduler、双前端、身份和回滚门禁通过。

完整发布与回滚约束以 K8s 仓库 Architecture v2 执行基线为准。
