import { createContext, useContext, useMemo, useState } from "react";

const messages = {
  "zh-CN": {
    home: "首页",
    reference: "参考页面",
    workspace: "工作台",
    logout: "退出登录",
    collapse: "收起菜单",
    expand: "展开菜单",
    openMenu: "打开菜单",
    theme: "主题",
    themeLight: "浅色",
    themeDark: "深色",
    themeSystem: "跟随系统",
    showTabs: "显示标签页",
    showBreadcrumb: "显示面包屑",
    settings: "界面设置",
  },
  en: {
    home: "Home",
    reference: "Reference",
    workspace: "Workspace",
    logout: "Sign out",
    collapse: "Collapse menu",
    expand: "Expand menu",
    openMenu: "Open menu",
    theme: "Theme",
    themeLight: "Light",
    themeDark: "Dark",
    themeSystem: "System",
    showTabs: "Show tabs",
    showBreadcrumb: "Show breadcrumb",
    settings: "Interface settings",
  },
} as const;

type Locale = keyof typeof messages;
type MessageKey = keyof (typeof messages)["zh-CN"];

interface LocaleContextValue {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: (key: MessageKey) => string;
}

const LocaleContext = createContext<LocaleContextValue | null>(null);

export function LocaleProvider({ children }: { children: React.ReactNode }) {
  const initial = import.meta.env.VITE_DEFAULT_LOCALE === "en" ? "en" : "zh-CN";
  const [locale, setLocale] = useState<Locale>(initial);
  const value = useMemo(
    () => ({
      locale,
      setLocale,
      t: (key: MessageKey) => messages[locale][key],
    }),
    [locale],
  );
  return (
    <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>
  );
}

export function useLocale(): LocaleContextValue {
  const context = useContext(LocaleContext);
  if (!context) throw new Error("useLocale must be used inside LocaleProvider");
  return context;
}
