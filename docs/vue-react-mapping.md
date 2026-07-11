# Vue Admin -> React Admin 对照

目标是让熟悉 Vue 模板的人快速定位同一概念，而不是用 React 模拟 Vue。

| Vue Admin                      | React Admin                     | 说明                                          |
| ------------------------------ | ------------------------------- | --------------------------------------------- |
| `src/main.ts` + `App.vue`      | `app/root.tsx`                  | 全局 Provider、文档壳和 ErrorBoundary         |
| `src/router/index.ts`          | `app/routes.ts`                 | Framework Mode route config/typegen           |
| `src/layouts/default.vue`      | `app/components/app-shell.tsx`  | 侧栏、顶部、面包屑、标签和内容出口            |
| `src/layouts/single-page.vue`  | `routes/login.tsx` 等独立 route | 不进入 protected layout                       |
| `src/pages/*.vue`              | `app/routes/*.tsx`              | 每个 route module 自带 meta/loader/error 能力 |
| `router.beforeEach`            | protected layout `clientLoader` | 只改善导航；API 仍做最终授权                  |
| Pinia user store               | auth loader/session Query       | 用户身份是服务端状态，不持久化到 UI store     |
| Pinia tabs store               | `app/store/ui.ts`               | 仅标签、侧栏等 UI 偏好可持久化                |
| `ref/reactive`                 | `useState/useReducer`           | 组件本地交互状态                              |
| `computed`                     | 普通派生值/必要时 `useMemo`     | 不默认缓存所有计算                            |
| `watch`                        | 明确事件/必要时 `useEffect`     | 优先事件驱动，避免同步派生状态                |
| Element Plus                   | Ant Design 6                    | 企业 Admin 主组件库；对齐概念，不复制 API     |
| `ElTable` / `ElForm`           | `Table` / `Form`                | 服务端数据仍由 Query 管理                     |
| `ElDialog` / `ElDrawer`        | `Modal` / `Drawer`              | 保持熟悉的操作层级和关闭语义                  |
| `ElMessage` / `ElNotification` | Ant Design `App` context        | 禁止使用脱离 context 的静态全局调用           |
| `ElConfigProvider`             | Ant Design `ConfigProvider`     | 主题、locale 和组件默认值                     |
| Vue Router auto routes         | `app/routes.ts`                 | 路由显式、可审查、类型生成                    |
| `VITE_API_URL`                 | `VITE_API_URL`                  | 保持配置名可识别                              |
| `dist` + Nginx                 | `build/client` + Nginx          | 都是静态 SPA；React 无 Node runtime           |

保持对齐：导航层级、颜色/密度、登录跳转、表格/表单/Dialog、配置和镜像接口。

明确不对齐：Vue 自动导入、Composition API 形状、Pinia server-state、Element Plus API 形状、Electron/PWA 和演示插件。
