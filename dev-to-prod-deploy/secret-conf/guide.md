# Secret 与凭据

Git 只跟踪 required-secret-keys.txt 和 optional-secret-keys.txt，不跟踪值。生产值由密码
管理器或受控 Secret 流程提供，并通过权限为 0600 的临时 env 文件注入。

统一 Backend 角色使用最小权限凭据：

- migration：仅数据库 schema owner；
- API：API runtime DB、OIDC/session 及必要下游凭据；
- Worker：worker DB、broker 与任务所需 Provider 凭据；
- Scheduler：scheduler DB、broker 和调度所需最小凭据；
- Admin/Web 前端：不得获得 Backend、数据库或 Provider secret。

上线前检查 key 集合完全匹配、凭据不是开发值、轮换/吊销可执行、日志不打印 Secret，并在结束后
安全删除本地临时文件。禁止把 Secret 写入 .conf、ConfigMap、镜像 ARG/ENV 或证据文件。

