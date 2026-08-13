# ConfigMap 与非敏感运行参数

ConfigMap 由 release scaffold 生成并进入不可变 bundle。它适合保存日志级别、公开服务地址、
功能开关、cookie 名称、session namespace、允许的 Origin、Provider 非敏感 endpoint 等。

转换到生产时逐项核对：

- 内部 URL 使用 Kubernetes Service DNS，外部 URL 使用正式 HTTPS Origin；
- Admin 与 Web 的 OIDC client、cookie、session namespace、scope 和 Origin 保持隔离；
- Provider endpoint 指向正式环境，且 NetworkPolicy 已声明相应出口；
- 不存在 localhost、.invalid、测试身份、mock provider 或调试开关；
- ConfigMap 变更已形成新的 release hash。

密码、client secret、API key、数据库 DSN、broker 密码和对象存储密钥不得进入 ConfigMap。

