import { QueryClientProvider } from "@tanstack/react-query";
import { App as AntApp, ConfigProvider } from "antd";
import enUS from "antd/locale/en_US";
import zhCN from "antd/locale/zh_CN";
import { Links, Meta, Outlet, Scripts, ScrollRestoration } from "react-router";

import { LocaleProvider, useLocale } from "~/lib/i18n";
import { queryClient } from "~/lib/query-client";

import "antd/dist/reset.css";
import "./styles/app.css";

function AntDesignBoundary() {
  const { locale } = useLocale();
  return (
    <ConfigProvider
      locale={locale === "zh-CN" ? zhCN : enUS}
      theme={{
        token: { colorPrimary: "#1677ff", borderRadius: 6 },
        components: {
          Layout: { siderBg: "#001529", headerBg: "#ffffff" },
        },
      }}
    >
      <AntApp>
        <Outlet />
      </AntApp>
    </ConfigProvider>
  );
}

export function Layout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <head>
        <meta charSet="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <Meta />
        <Links />
      </head>
      <body>
        {children}
        <ScrollRestoration />
        <Scripts />
      </body>
    </html>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <LocaleProvider>
        <AntDesignBoundary />
      </LocaleProvider>
    </QueryClientProvider>
  );
}

export function HydrateFallback() {
  return (
    <main className="center-page" aria-busy="true">
      <p>正在加载管理后台…</p>
    </main>
  );
}

export function ErrorBoundary({ error }: { error: unknown }) {
  const message =
    error instanceof Error ? error.message : "Unexpected application error";
  return (
    <main className="center-page" role="alert">
      <section className="status-card">
        <p className="eyebrow">Application error</p>
        <h1>页面暂时不可用</h1>
        <p>{message}</p>
        <a className="button primary" href="/">
          返回首页
        </a>
      </section>
    </main>
  );
}
