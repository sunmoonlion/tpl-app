# App Platform Kubernetes deployment scaffold

本目录是统一 Backend 架构唯一活动的 Kubernetes 部署脚手架。目录名与长期
分支名解耦，可在删除施工分支后继续使用。旧 `k8s-scaffold/`、
`celeryworker-*` 和 `nodebullworker-*` 已从模板当前分支移除；历史提交和冻结标签仅供回滚，
不得重新复制进 Architecture v2 实例。

`deployment_config.py` 是实例部署配置语法的模板真相源。实例必须保留 App 总入口、组件
入口、`deploy-<app>-app-all.conf` 和 `profiles/{KIND,C1,production}.conf`，同时只维护一份
bundle/YAML。配置解析器禁止执行 shell、拒绝未知键，并要求配置中的镜像 digest、origin、
namespace、副本数和 release id 与已门禁的 `release.json` 完全一致；要改变这些值必须生成
和验收一个新 release，不能在部署时覆盖旧 bundle。

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

实例侧 `.conf` 不保存 Secret。KIND/C1/production 的 kubeconfig、超时等操作参数放在独立
profile；未完成真实集群门禁的 profile 必须以 `PROFILE_ENABLED=false` 明确禁用。

`--casdoor-namespace` 必须填写 Casdoor 实际所在 namespace（默认仅兼容当前开发环境的
`app-platform-dev`）。脚手架会据此生成跨 namespace 的 Casdoor egress policy；不能用应用
namespace 代替，否则 NetworkPolicy 启用后会阻断 OIDC backchannel。

## Secret

Secret 值不进入模板、Git、命令行或日志。创建权限为 `0600` 的 env 文件，键必须与生成的
`required-secret-keys.txt` 完全相符。不同运行角色使用不同数据库和 broker 键，但都存放于
一个 Kubernetes Secret；每个 Pod 只引用本角色所需的 key。

实例覆盖必须保留模板的分角色运行凭据引用，不得将它们改回共享 DATABASE_URL /
CELERY_BROKER_URL。B7m 补齐 Worker 的 release-id 注解；最终渲染测试同时核新就绪
检查、发布标识及领域挂载不丢失。Secret 的不同 key 不证明真实用户名/权限不同，
供给时仍须使用独立 principal，并执行独立撤销与最小权限验收；不要把旧共享凭据复制
到几个新 key 当作隔离。该源码更新不改变既有 bundle 或集群。

### 数据库分角色权限候选（B7o，尚未接部署）

`runtime_database_policy.py` 提供模板当前六张表的纯 GRANT 编译函数，按实际迁移后的
表/列清单精确匹配；未知、缺少或新增列均拒绝。API 的 Outbox UPDATE 仅授去重键列，
供现有 ON CONFLICT 幂等复用；不能改状态/租约。Worker 负责消费/回执/租约/死信，
不授删除回执/租约墓碑的权限；API/Worker 对版本表只读。Scheduler 不授 schema/表权限。
这不是行级/租户授权，也不阻止 API 直接修改其已获授权的去重键；授权谓词仍由应用实现。

**这不是现有数据库的迁移/撤权脚本。**编译器不连接数据库、不创建角色、不传密码、不改
default ACL，也不验证当前角色继承/PUBLIC/owner 的有效权限。只能在外部供给已证明
独立新身份、正确 owner、封闭 PUBLIC/默认权限后使用；给旧账号追加这些 GRANT 不会
消除旧宽权限。当前没有 apply 入口，也没有接到 deploy.py，不能据候选测试宣称集群已修复。
领域实例需要逐表/逐操作 overlay 和独立实测，禁止直接使用模板清单覆盖领域权限。

普通门禁 `python3 -m unittest discover -s k8s-deployment/tests -q` 自动包含编译器测试。
真实 PG 门禁在 `k8s-deployment/integration/test_runtime_database_policy_pg.py`，必须显式
执行；未配置隔离环境确认时失败，不跳过。它只接受本机 `127.0.0.1:55439/backlog_tests`
的测试管理员连接及 `RUNTIME_POLICY_TEST_CONFIRM=disposable-b7o-only`，还须先核对该
端口确为获准一次性容器，而非仅凭端口名断言安全。URL 通过
`RUNTIME_POLICY_TEST_DATABASE_URL` 供给，不写入仓库。

在 tpl-app 根用 Backend 既有环境执行：

```bash
tpl-backend/app/.venv/bin/python -m pytest \
  -c tpl-backend/app/pyproject.toml \
  k8s-deployment/integration/test_runtime_database_policy_pg.py -q -x
```

门禁创建随机命名的测试库、四个独立 LOGIN/密码，使用迁移身份实际跑模板单链迁移，
用 API/Worker 原 application 服务与真实 SQLSTATE 断言权限；测试结束逐个删除自身
对象，不 FORCE、CASCADE 或终止其他连接。该测试供给 fixture 不是业务凭据供给器。
目前尚未接远端 CI，不能把“有文件”写成每次提交已自动运行真实 PG 验收。

`integration/permission_pg_support.py` 是公共隔离测试工具，不导入任何 App 模块；
实例须在独立 Python 进程中传入自己的 Backend 路径和已评审的权限编译函数，避免
同名 `app` 包互相污染。模板确认域仍为 `disposable-b7o-only`；Info 使用
`disposable-b7p-only`，以及仅在新测试库中创建 `uuid-ossp` 的显式选项（旧迁移需要）。
两者共用上述精确端口/测试库与清理规则，不为业务环境提供 apply 入口。
Knowledge 验证使用独立确认域 `disposable-b7q-only`；同样仅连接获准的一次性 PG，
复用公共工具而不导入其他 App 的业务包。
Investment 验证使用 `disposable-b7r-only`，遵守相同精确目标与隔离清理规则；
真实 LangGraph checkpointer 也必须使用其测试 Worker 的独立连接，不可沿用管理员。

```bash
chmod 600 /secure/path/tpl-backend.env
python3 deploy.py plan --bundle /tmp/tpl-r3-bundle
python3 deploy.py apply \
  --bundle /tmp/tpl-r3-bundle \
  --secret-env-file /secure/path/tpl-backend.env \
  --kubeconfig "$HOME/.kube/kind-config"
```

默认 `--component all` 按完整顺序部署整个 App。同一入口也支持独立部署，不会维护
第二份清单：

```bash
python3 deploy.py apply --component backend-api ...
python3 deploy.py apply --component backend-worker ...
python3 deploy.py apply --component backend-scheduler ...
python3 deploy.py apply --component admin-frontend ...
python3 deploy.py apply --component web-frontend ...
python3 deploy.py apply --component migration ...
python3 deploy.py apply --component ingress ...
```

组件部署仍会先对 release hash、外部 Secret、前置资源和 NetworkPolicy 做同样校验；
它只从已锁定的 `20-runtime.yaml` 取出目标 Deployment/PDB/HPA，因此总量与单组件
部署不会漂移。

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
