# 数据流与状态所有权

```text
URL/Route -> identity/entry condition -> Page
Page -> typed API client -> Product API -> domain truth
Page <-> TanStack Query cache
Page <-> form/local interaction state
AppShell <-> Zustand UI preferences
```

## React Router

负责 URL、route module、lazy split、protected layout、导航 pending、route error 和进入条件。loader 不建设第二份业务缓存。

## TanStack Query

负责 API server state、cache、pagination、polling、mutation、invalidations 和后台刷新。Query key 必须包含资源 scope；登出/换身份时清理受权缓存。

## Zustand

只保存侧栏折叠、打开标签等不影响业务正确性的 UI 偏好。Run、Artifact、审批、用户身份和权限不得以 Zustand 为事实源。

## 表单与 URL

Ant Design Form 拥有未提交值；提交成功后 invalidate Query。可分享/可恢复的筛选分页进入 URL。禁止以按钮 disabled 代替后端幂等和并发条件更新。

## 错误

API 使用 `code/message_key/retryable/correlation_id/field_errors`。页面不解析自然语言决定业务逻辑，也不渲染不可信 HTML 错误正文。
