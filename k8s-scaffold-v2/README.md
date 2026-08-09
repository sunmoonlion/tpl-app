# Architecture v2 Kubernetes scaffold

本目录是统一 Backend 架构唯一活动的 Kubernetes 脚手架。旧 `k8s-scaffold/`、
`celeryworker-*` 和 `nodebullworker-*` 已从模板当前分支移除；历史提交和冻结标签仅供回滚，
不得重新复制进 Architecture v2 实例。

它生成一个 App 的以下运行角色：

- 一个 FastAPI Backend 镜像：API、Celery Worker、Scheduler、Migration；
- 两个独立 Next.js 前端：Admin、Web；
- 一个 Backend ConfigMap、一个 Backend Secret、一个 Backend Service；
- Admin/Web 各自的 Deployment、Service 和严格 TLS IngressRoute；
- 角色化 ServiceAccount、NetworkPolicy、PDB、HPA、资源和探针。

浏览器对两个站点的 `/api` 请求由 Traefik 同源转发到同一 Backend；Next.js SSR 使用
`BACKEND_INTERNAL_URL` 调用同一个 ClusterIP Service。Backend 仍以独立 cookie、OIDC client、
session namespace、scope 和 Origin policy 隔离 Admin/Web。

## 生成

镜像必须使用 Harbor 的不可变 digest，不能使用 tag：

```bash
python3 scaffold.py \
  --app tpl \
  --namespace architecture-v2-r3 \
  --release-id r3-001 \
  --backend-image 'harbor.example/app/tpl-backend@sha256:...' \
  --admin-image 'harbor.example/app/tpl-admin-frontend@sha256:...' \
  --web-image 'harbor.example/app/tpl-web-frontend@sha256:...' \
  --admin-origin 'https://tpl-admin.example.com' \
  --web-origin 'https://tpl.example.com' \
  --casdoor-origin 'https://identity.example.com' \
  --casdoor-namespace identity-system \
  --tls-secret tpl-frontend-tls \
  --output-dir /tmp/tpl-r3-bundle
```

输出包含 `00-prerequisites.yaml`、`10-migration.yaml`、`20-runtime.yaml`、
`30-network-policies.yaml`、`40-ingress.yaml`、`required-secret-keys.txt`、
`optional-secret-keys.txt` 和 `release.json`。`release.json` 锁定输入镜像 digest 和每个文件的
SHA-256。

`--casdoor-namespace` 必须填写 Casdoor 实际所在 namespace（默认仅兼容当前开发环境的
`app-platform-dev`）。脚手架会据此生成跨 namespace 的 Casdoor egress policy；不能用应用
namespace 代替，否则 NetworkPolicy 启用后会阻断 OIDC backchannel。

## Secret

Secret 值不进入模板、Git、命令行或日志。创建权限为 `0600` 的 env 文件，键必须与生成的
`required-secret-keys.txt` 完全相符。不同运行角色使用不同数据库和 broker 键，但都存放于
一个 Kubernetes Secret；每个 Pod 只引用本角色所需的 key。

```bash
chmod 600 /secure/path/tpl-backend.env
python3 deploy.py plan --bundle /tmp/tpl-r3-bundle
python3 deploy.py apply \
  --bundle /tmp/tpl-r3-bundle \
  --secret-env-file /secure/path/tpl-backend.env \
  --kubeconfig "$HOME/.kube/kind-config"
```

部署严格按 `prerequisites/secret/network -> migration -> runtime -> ingress` 执行。Migration
成功并采集日志后立即删除 Job，避免长期遗留 `Completed` Pod；失败时不部署运行时。

`cleanup` 只按当前 App 标签删除本脚手架管理的资源。删除 Namespace 还必须显式提供
`--delete-namespace`，避免误删共享 namespace。

## 安全边界

- 运行时 ServiceAccount 不挂载 Kubernetes token；
- 容器非 root、只读 root filesystem、drop `ALL` capabilities；
- 前端只可访问 Backend 与 DNS；Backend 角色只开放 DNS、声明的数据依赖、Casdoor
  backchannel、内部 provider 和 HTTPS；
- 只有 Traefik、两个前端和显式标注的 internal caller 可以连接 Backend API；
- Migration 只获得 migration DB key，不获得浏览器 OIDC 或 Worker 下游凭据；
- API、Worker、Scheduler 使用不同 DB/broker key，避免同一镜像等同于同一权限。

仓库单元测试只能验证策略结构；报文级 allow/deny 必须在真正实现 NetworkPolicy 的 CNI 上
验收。R3 使用一次性 `disableDefaultCNI: true` 的 KIND + Calico 环境执行该门禁，不能把
kindnetd 集群中“策略对象存在”误报为“策略已生效”。
