# tpl-app — AI 协作上下文

本文件只提供仓库级入口，不维护独立于其他 AI 工具的项目事实。

## 开始任务前

1. 阅读 `docs/README.md`。
2. 核对目标子仓代码、README、依赖锁、测试和当前 Git 状态。
3. 涉及 MoocManus、跨仓契约或前端迁移时，以 k8s 仓库的 v5 总体方案、实施计划、ADR、contracts 和 evidence 为准。

## 工作边界

- 模板只接收通用能力，不接收 Info、Knowledge、Research 领域代码。
- 接口事实来自代码/OpenAPI/schema 和 contract tests，不维护手写的第二份权威契约。
- 任何时刻只推进实施计划中一个已激活任务；代码、测试、证据和状态回填齐全后再进入下一项。
- 不输出或提交 token、cookie、client secret、signed URL、真实凭据或完整敏感响应。
- 安装、网络构建和 Git push 由项目负责人执行；本地提交和验证必须可追溯。

## 文档规则

项目状态只写入中性 `docs/` 或 k8s 权威文档。不要创建任何按 AI 工具命名的平行文档树。
