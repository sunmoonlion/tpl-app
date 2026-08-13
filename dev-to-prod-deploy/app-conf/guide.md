# App release 配置

App release 配置是一次正式发布的可审计索引，不是任意参数覆盖文件。

必须声明：

- App 逻辑名、namespace、release id；
- Backend/Admin/Web 三个不可变镜像 digest；
- Admin/Web/Casdoor 的规范 Origin；
- API、Worker、Scheduler、Admin、Web 的目标副本数；
- bundle 路径、部署入口和默认 profile。

这些值必须与 bundle 中的 release.json 一致。要改变镜像、Origin、副本数或 namespace，
必须重新生成并验收 release，不能在 apply 时覆盖。

环境 profile 只保存 kubeconfig 和超时。尚未完成真实 C1/production 门禁时必须保持
PROFILE_ENABLED=false，不得通过删除保护字段绕过。

