# Vue Admin -> React Admin 能力对齐矩阵

状态：`P0-007A2 / NOT_STARTED`  
Vue 基线：`tpl-admin-frontend@7f6194650282c1a21bba7038b7e89a5efbdd2c18`  
React 当前基线：`tpl-admin-frontend-react@fe8fc5cfd2a9d23f4f8a1bcd0465440b2341d85e`

本文件是 P0-007A2 的施工矩阵，不把 React 骨架误称为完整迁移。矩阵中的 `MUST` 项在没有 React 实现、测试和证据前不能标记为完成；`DEFER` 必须有明确理由、影响、owner 和后续任务。

## 状态定义

| 状态 | 含义 |
|---|---|
| `SKELETON` | P0-007A 已提供接入点或中性示例，但尚未完成 Vue 能力等价 |
| `MUST` | P0-007A2 必须完成的生产相关能力 |
| `IN_PROGRESS` | 已开始实现，仍缺测试/证据或能力不完整 |
| `ACCEPTED` | 实现、测试、可访问性和 clean-room 证据齐全 |
| `DEFER` | 非目标或 legacy 能力，已记录后续任务；不能被任何 App 依赖 |
| `REMOVE` | 明确不再保留，并记录替代方案和迁移影响 |

## 1. 平台、运行时和部署

| Vue 基线 | React 目标 | 要求 | 状态 | 验收证据 |
|---|---|---|---|---|
| `src/main.ts`, `src/App.vue` | `app/root.tsx`, providers | React Router、Ant Design、Query、i18n、error boundary 的 provider 顺序稳定 | `SKELETON` | typecheck + route smoke |
| `vite.config.ts`, `tsconfig*.json`, `eslint.config.ts`, `uno.config.ts` | `vite.config.ts`, `tsconfig.json`, `eslint.config.js` | strict、typegen、lint、路径和环境变量约定 | `MUST` | clean-room install/typecheck/lint |
| `mybuild/Dockerfile`, `mybuild/nginx.conf`, `nginx/` | `mybuild/Dockerfile`, `mybuild/nginx.conf`, security headers | 静态产物、history/base-path fallback、health、缓存和安全头 | `SKELETON` | Docker/Nginx/KIND smoke |
| `.env*`, K8s 配置接口 | `.env.example`, K8s 配置接口 | API URL、auth mode、base path、镜像和 Secret 名称可追踪；不提交凭据 | `MUST` | config positive/negative tests |
| `cypress/`, Vitest 约定 | `e2e/`, `tests/`, Playwright/Vitest | 单元、组件、浏览器、a11y 和产物测试分层 | `SKELETON` | test matrix and traces |

## 2. 应用壳、路由和身份

| Vue 基线 | React 目标 | 要求 | 状态 | 验收证据 |
|---|---|---|---|---|
| `src/layouts/default.vue` | `app/components/app-shell.tsx` | 侧栏、顶部、面包屑、内容出口、响应式密度、主题 | `SKELETON` | visual/keyboard smoke |
| `src/layouts/single-page.vue`, `src/layouts/404.vue` | `routes/login.tsx`, `forbidden.tsx`, `not-found.tsx` | public/protected 边界、错误状态和 return URL | `SKELETON` | auth/error E2E |
| `src/router/index.ts`, `src/pages/[...path].vue` | `app/routes.ts`, route modules | route metadata、lazy split、pending/error boundary、deep link | `SKELETON` | typegen/history fallback |
| `src/store/user.ts`, login hooks | `app/lib/auth.ts`, auth Query/loader | BFF session、CSRF、401/403、logout；不把 token 写入 local/session storage | `SKELETON` | security vectors + browser E2E |
| `src/store/tabs.ts`, `src/utils/i18n.ts` | `app/store/ui.ts`, `app/lib/i18n.tsx` | 仅 UI 偏好持久化；server state 不复制到 Zustand | `SKELETON` | refresh/language tests |

## 3. 通用组件能力

以下 Vue 目录中的生产相关能力均为 `MUST`；React 目标路径可以调整，但必须回填本矩阵。

| Vue 来源 | React 目标能力 | 关键行为 | 状态 |
|---|---|---|---|
| `el-admin-components/components/Avatar/*` | AvatarList/AvatarMenu | 用户头像、菜单、键盘和权限动作 | `MUST` |
| `components/Charts/*` | Chart adapter/components | ECharts 数据、空/加载/错误、resize 和无障碍替代 | `MUST` |
| `components/Description/*` | Description | label/value、响应式布局、空值和复制 | `MUST` |
| `components/Edtior/*` | Editor | 编辑、清理、错误和内容边界 | `MUST` |
| `components/Form/*` | Form/FormItem/FormLayout/schema | schema 表单、校验、字段错误、提交状态 | `MUST` |
| `components/Icon/*` | Icon registry/picker | 本地图标、Iconify、网络图标安全策略 | `MUST` |
| `components/Layouts/*` | Header/HeaderTabs/Breadcrumb | header、tabs、面包屑、导航状态 | `MUST` |
| `components/Menu/*` | Menu/SubMenu/Dropdown | active route、折叠、键盘、权限过滤 | `MUST` |
| `components/Notice/*` | Notice/Notification | 读写状态、队列、空/错误和可访问性 | `MUST` |
| `components/Player/*` | Audio/Video player | 媒体错误、暂停、权限和资源 URL 清理 | `MUST` |
| `components/Slide/*` | Progress/transition | 进度、动画、reduced-motion | `MUST` |
| `components/Table/*` | Table/TableColumn/drag | 列配置、分页、筛选、拖拽、服务端状态 | `MUST` |
| `components/Themes/*` | theme/locale/fullscreen settings | 主题、语言、全屏、配置持久化 | `MUST` |
| `components/Transition/*` | transition primitives | collapse/transition 的可访问性和 reduced-motion | `MUST` |

## 4. 指令、工具和状态语义

| Vue 来源 | React 目标 | 要求 | 状态 |
|---|---|---|---|
| `el-admin-components/directives/modules/{copy,debounce,draggable,flash,longPress,scrollText,throttle,waterMarker}.ts` | hooks/components/utilities | 逐项决定 React idiomatic 实现；禁止只因没有 Vue directive 就静默删除 | `MUST` |
| `src/utils/{color,format,index}.ts` | `app/lib/utils/*` | 颜色、格式、日期、错误和安全 URL 行为有单测 | `MUST` |
| `src/store/*` | Query + UI store + local state | 明确 server state/UI state/form state 归属，禁止领域事实只存内存 | `MUST` |
| `src/modules/pwa.ts` | React PWA strategy | 盘点三个 App 是否依赖；无依赖时形成 `DEFER` 或 `REMOVE` 决策 | `DEFER` |
| `electron/*` | Electron strategy | 盘点是否仍有产品需求；无需求不得带入静态 Admin 主链 | `DEFER` |

## 5. 路由和示例页面

示例页不等于业务页面，但不得无记录地消失。每个页面必须标记为通用能力示例、生产页面迁移输入、延期或移除。

| Vue 来源 | React 处置 | 状态 |
|---|---|---|
| `src/pages/index.vue`, `about.vue`, `login.vue`, `menus/**` | 中性 route/shell 示例或真实迁移输入 | `MUST` |
| `src/pages/components/**` | 对应组件验收页；不进入 App 业务 | `MUST` |
| `src/pages/directives/**` | 对应 utility/behavior 验收页；未采用能力需 ADR | `MUST` |
| `src/pages/players/**`, `notice/**`, `table/**`, `form/**`, `icon/**` | 组件行为和错误状态验收页 | `MUST` |
| `mock/*`, `src/assets/images/headers/*` | 仅测试 fixture；不得伪装真实业务成功 | `MUST` |

## 6. P0-007A2 退出条件

- [ ] Vue 基线 commit 和完整 `git ls-files` 清单已归档。
- [ ] 所有生产相关 `MUST` 行有 React target、行为说明、测试和 owner。
- [ ] 每个 `DEFER/REMOVE` 行有理由、影响、后续任务和依赖审查。
- [ ] React 组件/页面不携带 Info、Knowledge、Research 领域 DTO 或业务规则。
- [ ] 模板从干净目录可重复 install、typecheck、lint、unit、component、Playwright、a11y、Docker 和 Nginx smoke。
- [ ] 基础路由、权限、错误、加载/空/部分/拒绝/重试状态与 Vue 行为矩阵对齐。
- [ ] 生成固定 template commit 和 `TEMPLATE_MIGRATION_READY` 证据；在此之前禁止实例化三个业务 Admin。

