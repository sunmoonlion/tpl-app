# tpl-app 镜像构建手册

> 四个子模块统一使用 `mybuild/` 目录管理构建，结构完全一致。  
> **构建上下文均为子模块根目录**，所有命令须在对应子模块目录下执行。

---

## 快速开始

```bash
# 1. 进入子模块
cd tpl-admin-frontend   # 或其他三个模块

# 2. 构建（读取 mybuild/build.conf 中的配置）
cd mybuild && ./build-image.sh

# 3. 推送到 Harbor
./push-image.sh
```

---

## 命名规范

> **Harbor 项目名**：`k8s-images` 与 `apps` 全局二选一，不可混用。本文默认 `k8s-images`。

| 子模块 | 本地镜像名 | Harbor 全名 |
|---|---|---|
| tpl-admin-frontend | `tpl-admin-frontend:1.0.0` | `harbor.sunmoonai.com:30443/k8s-images/tpl-admin-frontend:<tag>` |
| tpl-admin-backend | `tpl-admin-backend:1.0.0` | `harbor.sunmoonai.com:30443/k8s-images/tpl-admin-backend:<tag>` |
| tpl-web-frontend | `tpl-web-frontend:1.0.0` | `harbor.sunmoonai.com:30443/k8s-images/tpl-web-frontend:<tag>` |
| tpl-web-backend | `tpl-web-backend:1.0.0` | `harbor.sunmoonai.com:30443/k8s-images/tpl-web-backend:<tag>` |

**Tag 规则**：`<git-sha>`（不可变，生产使用）+ `latest`（移动引用，仅开发联调）。  
**实例化**：`tpl-` 前缀由 `init.sh` 替换为业务名，同步修改各模块 `mybuild/build.conf` 中的 `IMAGE` 变量。

---

## build.conf 配置说明

每个子模块 `mybuild/build.conf` 控制本地构建行为，CI 不读取此文件。

| 模块 | 镜像名变量 | Tag 变量 |
|---|---|---|
| tpl-admin-frontend | `ADMIN_CSR_IMAGE` | `ADMIN_CSR_TAG` |
| tpl-admin-backend | `ADMIN_BACKEND_IMAGE` | `ADMIN_BACKEND_TAG` |
| tpl-web-frontend | `TPL_SSR_IMAGE` | `TPL_SSR_TAG` |
| tpl-web-backend | `WEB_BACKEND_IMAGE` | `WEB_BACKEND_TAG` |

**常用修改：**

```bash
# 切换到自动推送（构建完直接推 Harbor）
PUSH_IMAGES_AFTER_BUILD="true"

# 切换为 nerdctl（containerd 环境）
CONTAINER_RUNTIME="sudo nerdctl"
NERDCTL_NAMESPACE="k8s.io"

# 实例化时更新镜像名（以 admin-frontend 为例）
ADMIN_CSR_IMAGE="myapp-admin-frontend"
```

---

## 前置：Harbor 登录

推送镜像前须先登录 Harbor（本地会话内登录一次即可）：

```bash
# docker
docker login harbor.sunmoonai.com:30443

# nerdctl
sudo nerdctl login harbor.sunmoonai.com:30443
```

---

## 一、tpl-admin-frontend（React Router + Vite → nginx）

### 手动构建

```bash
cd tpl-admin-frontend

# 黄金命令（与脚本等价）
docker build -f mybuild/Dockerfile \
  --build-arg NODE_IMAGE=node:22.22.0-alpine \
  --build-arg NGINX_IMAGE=harbor.sunmoonai.com:30443/k8s-images/nginx:stable-alpine \
  --build-arg VITE_API_URL=http://localhost:8001 \
  -t tpl-admin-frontend:1.0.0 .

# 使用脚本（参数从 mybuild/build.conf 读取）
cd mybuild
./build-image.sh                      # 构建
./build-image.sh --tag 1.0.1          # 自定义 tag
./push-image.sh                       # 推送到 Harbor
./rebuild-and-run.sh                  # 重建并本地运行（http://localhost:8080）
```

**build-arg 说明：**

| 参数 | 说明 | 默认值 |
|---|---|---|
| `NODE_IMAGE` | Node 构建基础镜像 | `node:22.22.0-alpine` |
| `NGINX_IMAGE` | Nginx 运行基础镜像 | Harbor 固定镜像 |
| `VITE_API_URL` | Admin BFF 地址，构建时静态嵌入 bundle | 无，**必须传入** |
| `BASE_PATH` | 非根路径部署前缀 | `/` |

> `VITE_*` 构建时静态嵌入，**不同环境须构建不同镜像**。

### CI/CD（Kaniko）

```
--dockerfile    mybuild/Dockerfile
--context       <子模块根目录>
--build-arg     REGISTRY=harbor.sunmoonai.com:30443/k8s-images
--build-arg     VITE_API_URL=<环境 API 地址>
--destination   harbor.sunmoonai.com:30443/k8s-images/tpl-admin-frontend:<git-sha>
--destination   harbor.sunmoonai.com:30443/k8s-images/tpl-admin-frontend:latest
--insecure
--skip-tls-verify
```

---

## 二、tpl-admin-backend（FastAPI + Python 3.12）

### 手动构建

```bash
cd tpl-admin-backend

# 黄金命令
docker build -f mybuild/Dockerfile \
  --build-arg REGISTRY=harbor.sunmoonai.com:30443/k8s-images \
  -t tpl-admin-backend:1.0.0 .

# 使用脚本
cd mybuild
./build-image.sh
./build-image.sh --tag 1.0.1
./push-image.sh
./rebuild-and-run.sh                  # 重建并本地运行（http://localhost:8000）
```

**build-arg 说明：**

| 参数 | 说明 | 默认值 |
|---|---|---|
| `REGISTRY` | Docker 基础镜像仓库 | `harbor.sunmoonai.com:30443/k8s-images` |
| `PYTHON_VERSION` | Python 版本 | `3.12` |

> `app/uv.lock` 须提交到 Git，构建用 `--frozen` 严格锁定依赖。  
> 原 `app/Dockerfile` 保留供在 `app/` 目录内本地开发，CI 不引用。

### CI/CD（Kaniko）

```
--dockerfile    mybuild/Dockerfile
--context       <子模块根目录>
--build-arg     REGISTRY=harbor.sunmoonai.com:30443/k8s-images
--destination   harbor.sunmoonai.com:30443/k8s-images/tpl-admin-backend:<git-sha>
--destination   harbor.sunmoonai.com:30443/k8s-images/tpl-admin-backend:latest
--insecure
--skip-tls-verify
```

---

## 三、tpl-web-frontend（Next.js 16 SSR）

### 手动构建

```bash
cd tpl-web-frontend

# 黄金命令（--target 可省略，run-minimal 是最后一个 stage，默认构建）
docker build -f mybuild/Dockerfile \
  --build-arg REGISTRY=harbor.sunmoonai.com:30443/k8s-images \
  --build-arg NEXT_PUBLIC_API_URL=http://localhost:8000 \
  -t tpl-web-frontend:1.0.0 .

# 使用脚本
cd mybuild
./build-image.sh
./build-image.sh --tag 1.0.1
./push-image.sh
./rebuild-and-run.sh                  # 重建并本地运行（http://localhost:3000）
```

**build-arg 说明：**

| 参数 | 说明 | 默认值 |
|---|---|---|
| `REGISTRY` | Docker 基础镜像仓库 | `harbor.sunmoonai.com:30443/k8s-images` |
| `NODE_VERSION` | Node.js 版本 | `20.18.0` |
| `NEXT_PUBLIC_API_URL` | Web BFF 地址，构建时静态嵌入 | 无，**必须传入** |
| `NEXT_PUBLIC_APP_NAME` | 应用名称 | `tpl` |

> `NEXT_PUBLIC_*` 构建时静态嵌入，**不同环境须构建不同镜像**。  
> `next.config` 须配置 `output: 'standalone'`，否则 run-minimal 阶段产物不完整。

### CI/CD（Kaniko）

```
--dockerfile    mybuild/Dockerfile
--context       <子模块根目录>
--target        run-minimal
--build-arg     REGISTRY=harbor.sunmoonai.com:30443/k8s-images
--build-arg     NEXT_PUBLIC_API_URL=<环境 API 地址>
--destination   harbor.sunmoonai.com:30443/k8s-images/tpl-web-frontend:<git-sha>
--destination   harbor.sunmoonai.com:30443/k8s-images/tpl-web-frontend:latest
--insecure
--skip-tls-verify
```

---

## 四、tpl-web-backend（NestJS + TypeScript）

### 手动构建

```bash
cd tpl-web-backend

# 黄金命令（--target 可省略，run 是最后一个 stage，默认构建）
docker build -f mybuild/Dockerfile \
  --build-arg REGISTRY=harbor.sunmoonai.com:30443/k8s-images \
  -t tpl-web-backend:1.0.0 .

# 使用脚本
cd mybuild
./build-image.sh
./build-image.sh --tag 1.0.1
./push-image.sh
./rebuild-and-run.sh                  # 重建并本地运行（http://localhost:8000）
```

**build-arg 说明：**

| 参数 | 说明 | 默认值 |
|---|---|---|
| `REGISTRY` | Docker 基础镜像仓库 | `harbor.sunmoonai.com:30443/k8s-images` |
| `NODE_VERSION` | Node.js 版本 | `18.20.0` |
| `NPM_REGISTRY` | pnpm 包镜像源 | `https://registry.npmmirror.com` |

> **禁止** CI 引用 `mybuild/Dockerfile.original`，含 `--mount=type=cache` BuildKit 专属语法，Kaniko 不支持。  
> 运行时以非特权用户 `appuser` 启动。

### CI/CD（Kaniko）

```
--dockerfile    mybuild/Dockerfile
--context       <子模块根目录>
--target        run
--build-arg     REGISTRY=harbor.sunmoonai.com:30443/k8s-images
--destination   harbor.sunmoonai.com:30443/k8s-images/tpl-web-backend:<git-sha>
--destination   harbor.sunmoonai.com:30443/k8s-images/tpl-web-backend:latest
--insecure
--skip-tls-verify
```

---

## 代理配置

国内网络构建时，可通过 `--build-arg` 传入代理（所有模块支持）：

```bash
docker build -f mybuild/Dockerfile \
  --build-arg HTTP_PROXY=http://proxy.example.com:8080 \
  --build-arg HTTPS_PROXY=http://proxy.example.com:8080 \
  --build-arg NO_PROXY=harbor.sunmoonai.com,localhost \
  --build-arg REGISTRY=harbor.sunmoonai.com:30443/k8s-images \
  -t <image>:<tag> .
```

CI 中通过 Kaniko `--build-arg` 同样传入；`NO_PROXY` 须包含 Harbor 与 Gitee 内网地址。

---

## 安全规范

- **Harbor 认证**：CI 使用 `kaniko-registry-secret`（Robot Account）挂载至 `/kaniko/.docker/config.json`，不写入 Dockerfile 或 Git
- **运行时密钥**：数据库密码、Redis ACL、Casdoor Secret 等通过 K8s Secret/ConfigMap 注入，`.dockerignore` 须排除 `.env`
- **非 root**：tpl-web-backend 运行时使用 `appuser`，其余模块按需跟进
- **不引用 latest 生产**：生产镜像以 `<git-sha>` tag 为准

---

## GitOps 衔接与过渡期

**GitOps**：CI 构建完成后更新 `gitops-config` 中对应服务的 `image.tag` 为本次 `<git-sha>`，ArgoCD 自动 sync。

**过渡期**：Argo Workflows 上线前，Jenkins + Kaniko 按相同命名与 tag 规则执行。

---

## 实施 Checklist

```
□ 0. 确认 Harbor 项目名（k8s-images 或 apps），全局统一
□ 1. 将基础镜像推送到 Harbor（见下方预缓存清单）
□ 2. Harbor 登录：docker login harbor.sunmoonai.com:30443
□ 3. tpl-admin-frontend：确认 VITE_API_URL 值，修改 build.conf
□ 4. tpl-admin-backend：确认 app/uv.lock 已提交
□ 5. tpl-web-frontend：确认 NEXT_PUBLIC_API_URL 值，修改 build.conf
□ 6. tpl-web-backend：确认 CI 只引用主 Dockerfile
□ 7. 各模块本地 docker build 验证，确认容器可正常启动
□ 8. 推送测试镜像到 Harbor，验证 <name>:<git-sha> 格式正确
□ 9. 接入 Argo Workflows WorkflowTemplate，按各模块 CI/CD 参数配置
□ 10. 过渡期：Jenkins Pipeline 按相同命名/tag 规则执行
```

---

## Harbor 基础镜像预缓存清单

### Harbor 项目目录结构

所有镜像（基础镜像 + 应用镜像）统一推送到同一个 Harbor 项目：

```text
harbor.sunmoonai.com:30443
└── k8s-images/                         ← Harbor 项目（需提前在 Harbor UI 创建）
    ├── node:18.20.0-alpine             ← 基础镜像
    ├── node:20.18.0
    ├── node:20.18.0-alpine
    ├── python:3.12-slim
    ├── nginx:stable-alpine
    ├── tpl-admin-frontend:<git-sha>    ← 应用镜像
    ├── tpl-admin-backend:<git-sha>
    ├── tpl-web-frontend:<git-sha>
    └── tpl-web-backend:<git-sha>
```

> **前提**：在 Harbor UI 中确认 `k8s-images` 项目已存在且当前账号有推送权限。

### 批量推送基础镜像

```bash
# 登录 Harbor
docker login harbor.sunmoonai.com:30443

# 批量拉取并推送（在有外网访问的机器上执行）
HARBOR="harbor.sunmoonai.com:30443/k8s-images"

for img in \
  "node:18.20.0-alpine" \
  "node:20.18.0" \
  "node:20.18.0-alpine" \
  "python:3.12-slim" \
  "nginx:stable-alpine"; do
  name="${img%%:*}"   # node / python / nginx
  tag="${img##*:}"    # 18.20.0-alpine / 3.12-slim 等
  docker pull $img
  docker tag $img ${HARBOR}/${name}:${tag}
  docker push ${HARBOR}/${name}:${tag}
done
```

| 原始镜像 | Harbor 缓存路径 |
|---|---|
| `node:18.20.0-alpine` | `harbor.sunmoonai.com:30443/k8s-images/node:18.20.0-alpine` |
| `node:20.18.0` | `harbor.sunmoonai.com:30443/k8s-images/node:20.18.0` |
| `node:20.18.0-alpine` | `harbor.sunmoonai.com:30443/k8s-images/node:20.18.0-alpine` |
| `python:3.12-slim` | `harbor.sunmoonai.com:30443/k8s-images/python:3.12-slim` |
| `nginx:stable-alpine` | `harbor.sunmoonai.com:30443/k8s-images/nginx:stable-alpine` |
