# Development → Production deployment

本目录恢复并现代化原有的 dev→prod 操作手册。它描述当前 Architecture v2 的发布转换方法，
不恢复旧双 Backend、独立 worker 工程、生成 YAML 或可变镜像 tag。

## 配置分层

| 层 | 存放内容 | 不存放内容 |
| --- | --- | --- |
| App release 配置 | App、namespace、release id、不可变镜像 digest、Origin、副本数 | 密码、token、临时覆盖值 |
| 环境 profile | kubeconfig、超时、环境是否已通过门禁 | 业务配置、Secret |
| release bundle | ConfigMap、探针、资源、HPA/PDB、NetworkPolicy、Ingress、依赖声明 | 明文凭据 |
| 外部 Secret | 数据库、broker、OIDC、S3、Provider 凭据 | Git 可跟踪内容 |
| Provider/基础设施配置 | Casdoor、RAGFlow、对象存储、转换服务等独立 release 的参数 | 业务 App 的所有权数据 |

配置项比旧版少，是因为旧版把“组件是否启用、组件优先级、生成文件名、镜像 tag、双后端和
独立 worker 工程”也当成部署配置；这些已被统一 Backend、固定部署 DAG 和不可变 bundle
替代。生产确实不同的值没有消失，只是进入上述唯一职责层。

## 转生产顺序

1. 从已通过测试的源码提交构建三个镜像，并解析为 repository@sha256:...。
2. 用模板 scaffold 生成新的 release bundle，禁止修改已发布 bundle。
3. 更新 App release 配置，使其与 release.json 完全一致。
4. 创建或核对生产外部 Secret；Secret 值不得进入 Git、命令行历史或日志。
5. 完成数据库备份、迁移预检和 Provider 连通性检查。
6. 依次执行 plan、服务端 dry-run、migration、runtime、ingress。
7. 验证 Admin↔Backend 与 Web↔Backend 两条配对链、真实 OIDC、核心业务和回滚。
8. 只有全部证据通过后，才将 production profile 从禁用改为启用并提交。

各专题见 [app-conf](app-conf/guide.md)、[configmap-conf](configmap-conf/guide.md)、
[pvc-conf](pvc-conf/guide.md)、[secret-conf](secret-conf/guide.md) 与
[转换流程](转换流程.md)。

