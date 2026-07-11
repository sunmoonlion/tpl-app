# Vue Admin 迁移指南

## 原则

- 按 route/产品能力迁移，不逐行翻译 `.vue`。
- Vue 保持可回退；同一 v5 新功能不双写。
- 从冻结 template commit 实例化，记录 template -> app commit。
- API contract 与领域状态不因前端框架改变。

## 每个 App 的步骤

1. 盘点 Vue route、权限、API、状态、测试和部署。
2. 对照 `vue-react-mapping.md` 建立逐 route checklist。
3. 用固定模板生成 React 骨架，只替换 app name/API/audience/镜像配置。
4. 先迁移只读页面，再迁移有副作用的 Command 页面。
5. 为每个写操作验证授权、幂等、并发冲突、审计原因和错误恢复。
6. 完成功能、安全、可访问性、性能和 E2E 等价。
7. 独立部署 React 镜像，通过受控路由切换和回滚演练。
8. 观察期结束后才停止 Vue；删除必须另走 M1-412。

## 禁止事项

- 不在 Vue 页面内长期 mount React。
- 不从某个 App 反向复制业务目录作为模板。
- 不把 Vue Pinia 持久数据直接迁成 Zustand server-state。
- 不为了“看起来一样”复制已知缺陷、无用 demo、Electron/PWA 或自动导入体系。
- 不逐项包装 Ant Design 使其伪装成 Element Plus API；迁移页面直接采用 Ant Design 标准属性和可访问性语义。
