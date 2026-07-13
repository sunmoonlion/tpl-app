# tpl-app 文档入口

状态：当前有效

本目录是模板根仓唯一的工具无关文档入口。项目事实不得再按 Claude、Cursor、Codex 或其他 AI 工具分别复制。

## 权威顺序

1. 模板代码、依赖锁、测试和构建/部署配置。
2. 各子仓自身的 README 与代码内契约。
3. `k8s` 仓库中的 MoocManus v5 总体方案、实施计划、ADR 和版本化跨仓契约。
4. Git 历史仅用于审计，不代表当前状态。

React Admin 当前通用能力矩阵位于 `tpl-admin-frontend/docs/vue-react-capability-matrix.md`。Worker 使用说明继续位于根仓 `docs-worker/`。

## 维护规则

- 通用模板能力进入对应模板子仓；Info、Knowledge、Research 业务规则不得进入模板。
- 跨仓契约只在 k8s v5 contracts 中维护一个权威版本。
- 当前任务、状态、交接和证据只更新权威实施计划，不创建按 AI 工具命名的平行文档树。
- 文档与代码冲突时先核验代码和运行证据，再修正文档；不得让旧交接覆盖当前计划。
