import { QueryClientProvider } from "@tanstack/react-query";
import { App as AntApp, ConfigProvider, theme as antdTheme } from "antd";
import enUS from "antd/locale/en_US";
import zhCN from "antd/locale/zh_CN";
import { Links, Meta, Outlet, Scripts, ScrollRestoration } from "react-router";
import { useEffect, useState } from "react";

import { LocaleProvider, useLocale } from "~/lib/i18n";
import { queryClient } from "~/lib/query-client";
import { useUiStore, type ThemeMode } from "~/store/ui";

import "antd/dist/reset.css";
import "./styles/app.css";

function AntDesignBoundary() {
  const { locale } = useLocale();
  const { themeMode, themeColor } = useUiStore();
  const resolvedTheme = useResolvedTheme(themeMode);

  useEffect(() => {
    document.documentElement.dataset.theme = resolvedTheme;
    document.documentElement.style.setProperty("--primary", themeColor);
  }, [resolvedTheme, themeColor]);

  return (
    <ConfigProvider
      locale={locale === "zh-CN" ? zhCN : enUS}
      theme={{
        algorithm:
          resolvedTheme === "dark" ? antdTheme.darkAlgorithm : undefined,
        token: { colorPrimary: themeColor, borderRadius: 6 },
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

function useResolvedTheme(mode: ThemeMode): "light" | "dark" {
  const [systemDark, setSystemDark] = useState(false);

  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const update = () => setSystemDark(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);

  return mode === "system" ? (systemDark ? "dark" : "light") : mode;
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
