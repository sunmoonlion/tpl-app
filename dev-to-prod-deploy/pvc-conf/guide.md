# 持久化数据与 PVC

统一 Backend 的 API、Worker、Scheduler 和两个前端默认都是无状态工作负载，不应为源码、
日志、缓存或会话创建 PVC。会话放 Redis，领域数据放数据库，对象放 S3/MinIO。

只有有状态 Provider 明确要求时才使用 PVC，例如 Casdoor/RAGFlow 的受管依赖或文档处理工作区。
从开发转生产时必须单独确认：

- 数据所有者、StorageClass、容量、访问模式和扩容策略；
- 快照/备份、恢复演练、保留策略和删除保护；
- 多副本是否支持该访问模式；
- PVC 是否属于独立 Provider release，而不是被业务 App bundle 隐式创建。

生产 PVC 不得由“复制开发 PVC 名称”完成迁移；数据迁移与应用 release 必须分别验收。

