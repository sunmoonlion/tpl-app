# tpl-admin-frontend-react

SunmoonAI React Admin 生产模板 Spike。它与 Vue `tpl-admin-frontend` 在产品概念和部署接口上对齐，内部使用标准 React 架构。

## 固定边界

- React 19 + TypeScript strict。
- React Router 8 Framework Mode，`ssr: false`。
- Ant Design 6 作为企业 Admin 主组件库；Lucide 用于轻量图标。
- TanStack Query 管理 API server state；Zustand 仅管理 UI 偏好。
- 静态构建输出到 `build/client`，由 Nginx 服务；无 Node 生产运行时。
- 浏览器只调用产品 API，不调用 internal API，不持有 service credential。
- Vue 模板仍是 legacy 回退，本目录不覆盖它。

## 本地运行

复制 `.env.example` 为 `.env.local`，配置后运行：

```text
pnpm install
pnpm typecheck
pnpm lint
pnpm test
pnpm dev
```

仅开发/E2E 可使用 `VITE_AUTH_MODE=demo`；生产构建会拒绝该值。

## 质量门禁

```text
pnpm typecheck
pnpm lint
pnpm test
pnpm build
pnpm test:e2e
```

使用非根路径部署时，构建参数必须包含规范化的 `BASE_PATH`；模板会同步配置 Router basename、Vite asset base 和 Nginx history/assets fallback：

```text
BASE_PATH=/admin pnpm build
```

## 扩展入口

- 路由：`app/routes.ts`
- 页面：`app/routes/*.tsx`
- 通用组件：`app/components/`
- API/认证/Query：`app/lib/`
- 纯 UI 状态：`app/store/`
- 样式：`app/styles/app.css`
- 部署：`mybuild/`

进一步阅读：`docs/vue-react-mapping.md`、`docs/add-a-page.md`、`docs/data-flow.md`、`docs/migration-guide.md`。

## 基础镜像

React Router 8 构建基线要求 Node 22.22+。Dockerfile 通过 `NODE_IMAGE` 与 `NGINX_IMAGE` 分别注入构建/运行镜像；生产部署前必须将固定 digest 的 Node 镜像同步到 Harbor，不允许回退 Node 18。运行镜像仍只有 Nginx。
