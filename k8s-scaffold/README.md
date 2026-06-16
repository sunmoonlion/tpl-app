# k8s-scaffold 使用指南

一条命令生成新应用的完整 k8s 部署目录，无需手写重复代码。

---

## 快速开始

```bash
cd tpl-app/k8s-scaffold/

# 一次生成四个可开发组件、两个配套 Worker 和业务 App 总部署入口
./scaffold-full-app.sh research --output-dir /home/zymun/k8s/sunmoonai/app-platform

# 后端服务（NestJS / FastAPI，默认接入 DB、S3 和 Elasticsearch）
./scaffold.sh my-service 8000

# 需要平台 S3 对象存储的后端
./scaffold.sh document-service 8000 --with-object-storage

# 需要平台 Elasticsearch 的后端
./scaffold.sh search-service 8000 --with-elasticsearch

# Next.js 前端（有 Node.js 服务层，运行时读取环境变量）
./scaffold.sh my-web 3000 --type node-frontend

# Vite/React 纯静态前端（nginx，无运行时环境变量）
./scaffold.sh my-admin 80 --type static-frontend
```

---

## 参数说明

```
./scaffold.sh <APP_NAME> <PORT> [OPTIONS]
```

| 参数 | 说明 | 示例 |
|------|------|------|
| `APP_NAME` | 应用名称，kebab-case | `report-service` |
| `PORT` | 容器端口 | `8000` |
| `--type` | 应用类型，见下表 | `backend`（默认） |
| `--namespace` | 目标 namespace | `app-platform-dev`（默认） |
| `--registry` | 远程集群镜像仓库地址 | `harbor.sunmoonai.com`（默认） |
| `--image-project` | 镜像项目名 | `app-images`（默认） |
| `--output-dir` | 输出到指定目录 | `./`（默认） |
| `--no-configmap` | 不生成 ConfigMap | — |
| `--no-ingress` | 不生成 Ingress | — |
| `--no-pvc` | 不生成 PVC | — |
| `--with-object-storage` | 增加独立的 `<app>-s3` ConfigMap/Secret `envFrom` | — |
| `--with-elasticsearch` | 增加独立的 `<app>-elasticsearch` 配置、凭据和 CA 挂载 | — |
| `--with-database` | 增加独立 PostgreSQL/Redis 连接 Secret | — |
| `--without-object-storage` | 显式关闭 Backend 的 S3 接线 | — |
| `--without-elasticsearch` | 显式关闭 Backend 的 Elasticsearch 接线 | — |
| `--without-database` | 显式关闭 Backend 的数据库接线 | — |
| `--memory-request` | 内存请求（覆盖类型默认值） | `512Mi` |
| `--memory-limit` | 内存限制 | `1Gi` |
| `--cpu-request` | CPU 请求 | `200m` |
| `--cpu-limit` | CPU 限制 | `1000m` |

### 应用类型（`--type`）

| 类型 | 说明 | 默认资源配额 | ConfigMap |
|------|------|------------|-----------|
| `backend` | NestJS / FastAPI 等后端（**默认**） | 内存 256Mi/512Mi，CPU 100m/500m | 有 |
| `node-frontend` | Next.js（有 Node.js 进程，运行时读取 env） | 内存 256Mi/512Mi，CPU 100m/500m | 有 |
| `static-frontend` | Vite/React + nginx（构建时烧入，无运行时 env） | 内存 64Mi/128Mi，CPU 50m/200m | **无** |

Backend 默认启用数据库、对象存储和 Elasticsearch 接线。`--with-*`
可用于显式表达，`--without-*` 仅用于确实不需要
对应能力的特殊服务。

`scaffold-full-app.sh` 还会生成：

- `celeryworker-<app>-admin-backend`，复用 admin-backend 镜像。
- `nodebullworker-<app>-web-backend`，复用 web-backend 镜像。

两个 Worker 默认标记为已配置但不启动，需在 App 聚合配置中按集群显式启用。

对象存储接线不创建 Bucket 或凭据，只让 Deployment 引用 Data
Platform S3 Provisioner 创建的 `<app>-s3` ConfigMap 和 Secret。该选项只适用
于 Backend 或 Node 服务；静态前端使用时会被拒绝。

Elasticsearch 接线同样只负责 Deployment 接线，不创建索引或凭据。资源由
Backend 的 `search-access-bootstrap` 声明并调用 Data Platform Provisioner
创建。静态前端不得持有 Elasticsearch 凭据。

---

## 生成的目录结构

以 `./scaffold.sh report-service 8000` 为例，在当前目录生成：

```
resources/k8s-resource/
├── templates/
│   ├── app/report-service.yaml               ← Deployment + Service
│   ├── configMap/report-service-config.yaml  ← ConfigMap（需填 key）
│   ├── secret/report-service-secret.yaml     ← Secret（需填 key）
│   ├── secret/harbor-registry-secret.yaml
│   ├── pvc/report-service-pvc.yaml
│   ├── namespace/report-service-namespace.yaml
│   └── ingress/ingress.yaml                  ← 需填域名和路径
└── custom-values/
    ├── app/generate-app/
    │   ├── generate-app.conf                  ← 镜像配置（TAG 每次发版改）
    │   └── generate-app.sh
    ├── configMap/report-service-config/generate-report-service-config/
    │   ├── generate-report-service-config.conf  ← 需填配置值
    │   └── generate-report-service-config.sh    ← 需补 export 段
    ├── secret/report-service-secret/generate-report-service-secret/
    │   ├── generate-report-service-secret.conf  ← 需填密钥值
    │   └── generate-report-service-secret.sh    ← 需补 export 段
    ├── secret/harbor-registry-secret/generate-harbor-registry-secret/
    │   ├── generate-harbor-registry-secret.conf ← 需填 Harbor 密码
    │   └── generate-harbor-registry-secret.sh
    ├── pvc/report-service-pvc/generate-report-service-pvc/
    ├── namespace/report-service-namespace/generate-report-service-namespace/
    └── ingress/report-service-ingress/generate-ingress/
        ├── generate-ingress.conf              ← 需填域名
        └── generate-ingress.sh

deploy-report-service/
├── app/deploy-app/
│   ├── deploy-report-service.sh              ← 主部署脚本
│   └── deploy-report-service.conf            ← 需填 PROJECT_ID/NAMESPACE
├── secret/report-service-secret/deploy-report-service-secret/
├── secret/harbor-registry-secret/deploy-harbor-registry-secret/
├── configMap/report-service-config/deploy-report-service-config/
└── ingress/report-service-ingress/deploy-ingress/
```

---

## 生成后必须手工填写的文件

scaffold 结束时会打印编号清单，以下是每项的说明：

### 1. ConfigMap key 列表

**`templates/configMap/<app>-config.yaml`**

添加实际字段（非敏感配置）：

```yaml
data:
  NODE_ENV: "${NODE_ENV}"
  REDIS_HOST: "${REDIS_HOST}"
  CASDOOR_ENDPOINT: "${CASDOOR_ENDPOINT}"
```

### 2. ConfigMap 配置值

**`custom-values/configMap/.../generate-<app>-config.conf`**

填写每个字段的实际值（k8s 内部 DNS，不用 localhost）：

```bash
NODE_ENV="${NODE_ENV:-production}"
REDIS_HOST="${REDIS_HOST:-redis-sunmoonai.data-platform-dev.svc.cluster.local}"
CASDOOR_ENDPOINT="${CASDOOR_ENDPOINT:-https://casdoor.sunmoonai.com}"
```

### 3. ConfigMap export 段

**`custom-values/configMap/.../generate-<app>-config.sh`**

在文件中的 `# TODO` 注释下添加（每个 key 一行）：

```bash
export NODE_ENV="${NODE_ENV:-}"
export REDIS_HOST="${REDIS_HOST:-}"
export CASDOOR_ENDPOINT="${CASDOOR_ENDPOINT:-}"
```

> **为什么要加 export？** generate 脚本用 `envsubst` 替换 YAML 模板里的变量，`envsubst` 只识别已 `export` 的变量。

### 4. Secret key 列表

**`templates/secret/<app>-secret.yaml`**

添加敏感字段：

```yaml
stringData:
  DATABASE_URL: "${DATABASE_URL}"
  REDIS_PASSWORD: "${REDIS_PASSWORD}"
  CASDOOR_CLIENT_SECRET: "${CASDOOR_CLIENT_SECRET}"
```

### 5. Secret 密钥值

**`custom-values/secret/<app>-secret/.../generate-<app>-secret.conf`**

填写真实密码（此文件不应提交到 git）：

```bash
DATABASE_URL="${DATABASE_URL:-postgresql://user:password@postgresql.svc:5432/dbname}"
REDIS_PASSWORD="${REDIS_PASSWORD:-realpassword}"
CASDOOR_CLIENT_SECRET="${CASDOOR_CLIENT_SECRET:-realsecret}"
```

### 6. Secret export 段

**`custom-values/secret/<app>-secret/.../generate-<app>-secret.sh`**

同第 3 步，补充 export 语句：

```bash
export DATABASE_URL="${DATABASE_URL:-}"
export REDIS_PASSWORD="${REDIS_PASSWORD:-}"
export CASDOOR_CLIENT_SECRET="${CASDOOR_CLIENT_SECRET:-}"
```

### 7. Harbor Registry 密码

**`custom-values/secret/harbor-registry-secret/.../generate-harbor-registry-secret.conf`**

```bash
DOCKER_SERVER="harbor.sunmoonai.com"
KIND_DOCKER_SERVER="harbor.sunmoonai.com:30443"
DOCKER_USERNAME="admin"
DOCKER_PASSWORD="realpassword"
```

新增 app 不要写死 `harbor.sunmoonai.com:30443`。部署入口只传 `kind` 或 `c1`，生成的脚本会通过 `k8s/utils/cluster-config-mapping.sh` 中的 `get_cluster_harbor_registry` 自动解析：

- `KIND` -> `harbor.sunmoonai.com:30443`
- `C1/C2/C3` -> `harbor.sunmoonai.com`

### 8. Ingress 域名和路径

**`templates/ingress/ingress.yaml`**

修改 `PathPrefix`（后端通常 `/api`，前端通常 `/`）：

```yaml
- match: Host(`{{NODE_IP}}`) && PathPrefix(`/api`)
```

**`custom-values/ingress/.../generate-ingress.conf`**

```bash
UNIFIED_HOST="api.myapp.sunmoonai.com"
NODE_IP="101.126.151.0"
SERVICE_PORT="8000"
```

### 9. 部署配置

**`deploy-<app>/app/deploy-app/deploy-<app>.conf`**

```bash
MY_SERVICE_PROJECT_ID="sunmoonai"
MY_SERVICE_NAMESPACE="app-platform-dev"
ENVIRONMENT="development"
```

---

## 部署

填写完成后，在有 kubectl 权限的机器上执行：

```bash
cd deploy-<app>/app/deploy-app/
./deploy-<app>.sh deploy <project_id> <namespace> <environment>

# 示例
./deploy-report-service.sh deploy sunmoonai app-platform-dev development
```

脚本自动完成：Namespace → Harbor Secret → App Secret → ConfigMap → Ingress → PVC → Deployment/Service

---

## 示例：完整接入一个新后端服务

```bash
# 1. 生成目录
cd tpl-app/k8s-scaffold/
./scaffold.sh report-service 8000 \
  --output-dir /path/to/k8s/my-project/report-service/

# 2. 按 scaffold 输出的 TODO 清单填写 9 个文件
#    （ConfigMap key/值/export + Secret key/值/export + Harbor 密码 + Ingress + deploy.conf）

# 3. 构建并推送镜像
cd /path/to/report-service-src/mybuild/
./push-image.sh --tag 1.0.0

# 4. 部署
cd /path/to/k8s/my-project/report-service/deploy-report-service/app/deploy-app/
./deploy-report-service.sh deploy sunmoonai app-platform-dev development

# 5. 验证
kubectl get pods -n app-platform-dev -l app=report-service
```

---

## 占位符说明（供修改 tpl 文件时参考）

scaffold 用 `sed` 替换 `tpl/` 中的以下占位符：

| 占位符 | 替换为 | 示例 |
|--------|--------|------|
| `__APP_NAME__` | 应用名（kebab-case） | `report-service` |
| `__APP_NAME_UPPER__` | 应用名（UPPER_SNAKE_CASE） | `REPORT_SERVICE` |
| `__PORT__` | 端口号 | `8000` |
| `__NAMESPACE__` | namespace | `app-platform-dev` |
| `__REGISTRY__` | 远程集群镜像仓库地址 | `harbor.sunmoonai.com` |
| `__KIND_REGISTRY__` | Kind 镜像仓库地址 | `harbor.sunmoonai.com:30443` |
| `__IMAGE_PROJECT__` | 镜像项目名 | `app-images` |
| `__MEMORY_REQUEST__` | 内存请求 | `256Mi` |
| `__MEMORY_LIMIT__` | 内存限制 | `512Mi` |
| `__CPU_REQUEST__` | CPU 请求 | `100m` |
| `__CPU_LIMIT__` | CPU 限制 | `500m` |

`tpl/` 文件中的 `${...}` 语法不会被触碰，它们是生成后的 YAML 里供 `envsubst` 使用的变量。
