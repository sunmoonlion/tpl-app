# 新增页面

## 1. 新建 route module

在 `app/routes/example.tsx` 创建组件。页面服务端数据使用 TanStack Query；只有进入页面前必须完成的身份/范围检查放入 loader。

## 2. 注册路由

在 `app/routes.ts` 增加：

```text
route('example', './routes/example.tsx')
```

受保护页面放在 protected layout 的 children 中。公开页面与 login 同级。

## 3. 加入菜单

在 `app/components/app-shell.tsx` 的 `navItems` 添加路径、message key 和图标。生产模板后续可把菜单元数据独立成配置，但在需求出现前不建设动态菜单平台。

## 4. 使用 URL 保存视图

分页、筛选、排序放 search params；Query 管理返回数据；表单草稿留在组件/表单层；不要把 API 响应复制到 Zustand。

基础后台交互优先使用 Ant Design 6 的 Table、Form、Modal、Drawer、Result、Empty 和 ConfigProvider；不要同时引入另一套完整 UI 库。只有 Ant Table 被真实规模证明不足时，才为单一场景评估专项 Data Grid。

## 5. 验收

至少增加 route/component 测试、权限负例、错误/空状态和 Playwright 主路径。运行 typecheck、lint、test、build。
