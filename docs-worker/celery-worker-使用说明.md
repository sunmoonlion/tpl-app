# Celery Worker 使用说明

## 定位

Celery Worker 用于 Python 技术栈的 backend，例如 `admin-backend`。它和对应 backend 使用同一个业务镜像，复用同一套业务代码、数据库配置、Redis 配置和应用 Secret，只是容器启动命令不同：

```bash
celery -A <CELERY_APP_MODULE> worker -Q <CELERY_QUEUE>
```

在当前模板中，Celery Worker 目录命名为：

```text
celeryworker-<app-name>-admin-backend
```

Node.js 的 `web-backend` 不使用这个组件，应该使用 `nodebullworker-<app-name>-web-backend`。

## 架构

```text
admin-backend API
  -> RabbitMQ vhost / queue
  -> celeryworker-<app-name>-admin-backend
  -> 同一套业务数据库 / Redis / 对象存储 / 外部服务
```

关键原则：

- Producer 和 Worker 按 backend 隔离账号。
- RabbitMQ 由 `messaging-platform/rabbitmq` 统一部署。
- vhost、用户、权限、队列由 RabbitMQ app definitions 统一创建。
- Worker 不单独维护数据库账号，默认复用对应 backend 的 ConfigMap/Secret。
- Worker 镜像默认复用对应 backend 镜像，保证任务代码和业务代码版本一致。

## RabbitMQ

RabbitMQ 不在 Celery Worker 组件内创建。队列拓扑由：

```text
k8s/sunmoonai/messaging-platform/rabbitmq/resources/custom-values/app-definitions-<environment>.yaml
```

统一维护。

推荐生产隔离模型：

```text
vhost: <app-name>-<environment>
producer user: <app-name>-admin-backend-producer
worker user:   <app-name>-admin-backend-worker
queue:         <app-name>.admin.default
```

Producer 只需要写队列权限，Worker 只需要消费队列权限。不要让 backend 和 worker 共用 RabbitMQ 超级用户。

## 关键配置

Celery Worker 自身配置在组件 ConfigMap/Secret 中：

```text
CELERY_APP_MODULE
CELERY_QUEUE
CELERY_CONCURRENCY
CELERY_LOG_LEVEL
CELERY_INCLUDE_MODULES
CELERY_BROKER_URL
CELERY_RESULT_BACKEND
```

业务配置来自对应 backend：

```text
<app-name>-admin-backend-config
<app-name>-admin-backend-secret
```

因此任务里需要访问数据库、Redis、对象存储、LLM Key 等配置时，不应在 Worker 里重复声明，应该继续从 backend 的配置读取。

## 任务代码

任务代码必须在 backend 镜像内。推荐做法是在 backend 仓库中维护 Celery app 和 tasks，例如：

```text
app/
  worker.py
  tasks/
    __init__.py
    mail.py
    report.py
```

`CELERY_APP_MODULE` 指向 Celery app 所在模块，例如：

```text
app.worker
```

如果任务分散在多个模块，使用：

```text
CELERY_INCLUDE_MODULES="app.tasks.mail,app.tasks.report"
```

不要把任务代码复制到 Worker 部署目录。Worker 部署目录只负责 Kubernetes 部署，不承载业务任务源码。

## 部署

单独部署：

```bash
cd celeryworker-<app-name>-admin-backend/deploy-celeryworker-<app-name>-admin-backend/app/deploy-app
./deploy-celeryworker-<app-name>-admin-backend.sh deploy
```

随 app 一起部署：

```bash
cd k8s/sunmoonai/app-platform/<app-name>-app/deploy-<app-name>-app-all
./deploy-<app-name>-app-all.sh --cluster C1 deploy
```

是否启用由 `deploy-<app-name>-app-all.conf` 控制：

```bash
C1_celeryworker_<app_name>_admin_backend_enabled="true"
KIND_celeryworker_<app_name>_admin_backend_enabled="true"
```

部署前需先 **重建并推送 admin-backend 镜像**（镜像内含 `celery` 与 `app/worker.py`）。

## 扩缩容

优先通过 Kubernetes Deployment replicas 扩容 Worker。Celery 进程内并发由 `CELERY_CONCURRENCY` 控制。

建议：

- CPU 密集任务：降低 `CELERY_CONCURRENCY`，增加 Pod 数。
- IO 密集任务：可以适当提高 `CELERY_CONCURRENCY`。
- 长任务：开启合理的 ack、超时和幂等策略，避免任务丢失或重复执行不可控。

## 运维检查

查看 Pod：

```bash
kubectl get pods -n app-platform-dev -l app=celeryworker-<app-name>-admin-backend
```

看日志：

```bash
kubectl logs -n app-platform-dev -l app=celeryworker-<app-name>-admin-backend -f
```

检查 RabbitMQ：

- vhost 是否存在。
- worker 用户是否能消费目标 queue。
- producer 用户是否能写入目标 queue。
- queue 是否有积压。
- Worker 日志是否有 import error 或 broker auth error。

## 常见问题

`ModuleNotFoundError`：任务模块没有打进 backend 镜像，或 `CELERY_APP_MODULE` / `CELERY_INCLUDE_MODULES` 写错。

`ACCESS_REFUSED`：RabbitMQ 用户、密码、vhost 或权限不匹配，优先检查 app definitions。

任务能入队但不执行：检查 `CELERY_QUEUE` 是否和 producer 投递的 routing key/queue 一致。

任务访问数据库失败：Worker 复用 backend Secret，检查对应 backend 的 DB 配置是否完整，以及 Worker 是否 envFrom 了 backend ConfigMap/Secret。

