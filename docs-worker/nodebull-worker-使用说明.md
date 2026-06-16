# Node Bull Worker 使用说明

## 定位

Node Bull Worker 用于 Node.js 技术栈的 `web-backend`。当前 `web-backend` 已内置 NestJS Bull + Redis 队列能力，Worker 只需要用同一个 web-backend 镜像启动独立的 Nest application context。

目录命名为：

```text
nodebullworker-<app-name>-web-backend
```

它不是 Python Celery，也不使用 RabbitMQ。当前队列后端是 Redis，队列实现是：

```text
@nestjs/bull + bull + ioredis
```

## 架构

```text
web-backend API
  -> Bull queue: scheduled-tasks
  -> redis-nodebull
  -> nodebullworker-<app-name>-web-backend
  -> 同一套业务数据库 / 业务缓存 / 对象存储 / 外部服务
```

关键原则：

- Worker 和 web-backend 使用同一个镜像，保证任务代码版本一致。
- HTTP API 进程默认不承担队列消费职责。
- HTTP API 如需投递任务，设置 `QUEUE_ENABLED=true` 加载 Bull producer。
- Worker 通过 `QUEUE_ON=true` 或 `QUEUE_CONSUMER_ON=true` 注册 Bull consumer。
- 队列 Redis 必须使用 `QUEUE_REDIS_*`，不复用 web-backend 的业务/session/cache Redis。
- NodeBull 专用 Redis 实例由 `data-platform/redis` 部署为 `redis-nodebull`。

## 代码入口

web-backend 中的独立入口：

```text
app/src/worker.ts
```

它使用：

```ts
NestFactory.createApplicationContext(AppModule)
```

只启动依赖注入和 provider，不监听 HTTP 端口。构建后 Kubernetes 直接启动：

```bash
node dist/worker
```

本地或手工运行也可以用：

```bash
pnpm run start:worker
```

## 队列代码

当前 Bull 模块位置：

```text
app/src/conditional/queue/queue.module.ts
app/src/conditional/queue/services/scheduled-tasks.consumer.ts
app/src/conditional/queue/services/scheduled-tasks-events.service.ts
```

当前队列名：

```text
scheduled-tasks
```

当前任务处理器：

```text
sendMail
sendSms
```

新增任务时，在 `scheduled-tasks.consumer.ts` 增加 `@Process('<job-name>')` 方法，并在 producer 侧向同一队列投递同名 job。

## 关键配置

Node Bull Worker 自身 ConfigMap 只保留运行模式：

```text
NODE_ENV=production
QUEUE_ON=true
```

HTTP API Pod 如果只投递任务、不消费任务，应使用：

```text
QUEUE_ENABLED=true
QUEUE_ON=false
```

业务配置来自对应 web-backend：

```text
<app-name>-web-backend-config
<app-name>-web-backend-secret
```

Bull Redis 读取顺序：

```text
QUEUE_REDIS_HOST
QUEUE_REDIS_PORT
QUEUE_REDIS_USERNAME
QUEUE_REDIS_PASSWORD
QUEUE_REDIS_DB
QUEUE_REDIS_PREFIX
```

缺少 `QUEUE_REDIS_HOST` 或 `QUEUE_REDIS_PORT` 时，`QUEUE_ON=true` 的进程会启动失败。这样可以避免误把 Bull 队列写入业务 Redis。

## Kubernetes 部署

Deployment 使用同一个 web-backend 镜像：

```text
harbor.sunmoonai.com:30443/k8s-images/<app-name>-web-backend:<tag>
```

容器命令：

```bash
set -eu
export NODE_ENV="${NODE_ENV:-production}"
export QUEUE_ON="${QUEUE_ON:-true}"
exec node dist/worker
```

组件同时 envFrom：

```text
<app-name>-web-backend-config
<app-name>-web-backend-secret
nodebullworker-<app-name>-web-backend-config
nodebullworker-<app-name>-web-backend-secret
<app-name>-web-backend-nodebull-redis-conn
```

Worker Secret 当前为空 Secret，保留它是为了部署结构统一；队列 Redis 敏感配置来自 `db-provisioner` 生成的 `*-nodebull-redis-conn` Secret。

## NodeBull Redis 开通

先部署专用 Redis 实例：

```bash
cd /home/zym/k8s/sunmoonai/data-platform
./deploy-data-platform-all/deploy-data-platform-all.sh deploy sunmoonai data-platform-dev development
```

也可以单独部署：

```bash
cd /home/zym/k8s/sunmoonai/data-platform/redis/deploy-redis
./deploy-redis.sh deploy nodebull data-platform-dev development
```

然后为 app 创建 NodeBull Redis ACL 用户和连接 Secret：

```bash
cd /home/zym/<app-name>-app/<app-name>-web-backend
ENABLE_NODEBULL_REDIS=true ./db-access-bootstrap/setup-k8s-db-access.sh
```

配置文件位于：

```text
db-access-bootstrap/config/nodebull-redis.k8s.env
```

## deploy-all

随 app 一起部署时，由 `deploy-<app-name>-app-all.conf` 控制：

```bash
C1_nodebullworker_<app_name>_web_backend_enabled="true"
KIND_nodebullworker_<app_name>_web_backend_enabled="true"
```

优先级建议排在 web-backend 之后，确保 backend 的 ConfigMap/Secret 先存在。

## 生产建议

默认推荐独立 Worker Pod，而不是在 HTTP Pod 里同时消费队列。原因：

- API 扩缩容和任务消费扩缩容可以分开。
- 长任务不会影响 HTTP 请求延迟。
- Worker 可以部署在能访问内网资源的位置，API 可以部署在云端。
- Pod 资源限制可以按任务负载单独设置。
- 失败重启不会影响 API 服务。

如果任务非常轻、流量很小，也可以让 HTTP 进程开启 `QUEUE_ON=true` 直接消费，但这不是默认生产形态。

## 运维检查

查看 Pod：

```bash
kubectl get pods -n app-platform-dev -l app=nodebullworker-<app-name>-web-backend
```

看日志：

```bash
kubectl logs -n app-platform-dev -l app=nodebullworker-<app-name>-web-backend -f
```

检查 Redis：

- `QUEUE_REDIS_*` 是否来自 `*-nodebull-redis-conn` Secret。
- Redis Service 是否为 `redis-nodebull-master.data-platform-dev.svc.cluster.local`。
- Worker 日志是否能连接 Redis。
- Bull 队列 `scheduled-tasks` 是否有积压。
- producer 投递的 job name 是否和 `@Process()` 名称一致。

## 常见问题

Worker 启动但不消费：确认 `QUEUE_ON=true`，并确认 `getEnvs()` 能读取运行时环境变量。

Redis 连接失败：检查 `QUEUE_REDIS_*` 配置、`redis-nodebull` Pod/Service、以及 app 的 `*-nodebull-redis-conn` Secret 是否已经创建。

任务代码找不到：Worker 使用 web-backend 镜像，必须重新构建并推送包含最新任务代码的 web-backend 镜像。

任务重复执行：Bull 默认至少一次执行语义，任务处理逻辑要尽量幂等，尤其是发消息、扣款、写状态这类副作用任务。

HTTP Pod 也在消费任务：检查 web-backend Deployment 是否设置了 `QUEUE_ON=true`。生产上应让 HTTP Pod 关闭消费，只由 `nodebullworker-*` 消费。
