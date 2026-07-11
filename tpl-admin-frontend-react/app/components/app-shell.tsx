import {
  Avatar,
  Breadcrumb,
  Button,
  Dropdown,
  Layout,
  Menu as AntMenu,
  Space,
  Tabs,
  Typography,
} from "antd";
import {
  ChevronRight,
  Home,
  Languages,
  LogOut,
  Menu,
  Table2,
  X,
} from "lucide-react";
import { useEffect } from "react";
import { Outlet, useLocation, useNavigate } from "react-router";

import type { AuthUser } from "~/lib/auth";
import { logoutUrl } from "~/lib/auth";
import { appConfig } from "~/lib/config";
import { useLocale } from "~/lib/i18n";
import { useUiStore } from "~/store/ui";

const navItems = [
  { path: "/", labelKey: "home" as const, icon: Home },
  { path: "/reference", labelKey: "reference" as const, icon: Table2 },
];

export function AppShell({ user }: { user: AuthUser }) {
  const location = useLocation();
  const navigate = useNavigate();
  const { locale, setLocale, t } = useLocale();
  const { sidebarCollapsed, tabs, toggleSidebar, addTab, removeTab } =
    useUiStore();
  const activeItem = navItems.find((item) => item.path === location.pathname);

  useEffect(() => {
    if (activeItem) {
      addTab({ path: activeItem.path, label: t(activeItem.labelKey) });
    }
  }, [activeItem, addTab, t]);

  return (
    <Layout className="app-shell">
      <Layout.Sider
        className="sidebar"
        collapsed={sidebarCollapsed}
        width={252}
        collapsedWidth={68}
        trigger={null}
        aria-label="主导航"
      >
        <div className="brand">
          <span className="brand-mark">S</span>
          {!sidebarCollapsed && <strong>{appConfig.name}</strong>}
        </div>
        <AntMenu
          mode="inline"
          theme="dark"
          selectedKeys={[location.pathname]}
          onClick={({ key }) => void navigate(key)}
          items={navItems.map(({ path, labelKey, icon: Icon }) => ({
            key: path,
            icon: <Icon aria-hidden="true" size={18} />,
            label: t(labelKey),
          }))}
        />
      </Layout.Sider>

      <Layout className="workspace">
        <Layout.Header className="topbar">
          <Button
            type="text"
            icon={
              sidebarCollapsed ? <ChevronRight size={20} /> : <Menu size={20} />
            }
            onClick={toggleSidebar}
            aria-label={sidebarCollapsed ? t("expand") : t("collapse")}
          />
          <Breadcrumb
            items={[
              { title: appConfig.name },
              { title: activeItem ? t(activeItem.labelKey) : "Page" },
            ]}
          />
          <Space className="topbar-actions">
            <Button
              type="text"
              icon={<Languages size={17} />}
              onClick={() => setLocale(locale === "zh-CN" ? "en" : "zh-CN")}
            >
              {locale === "zh-CN" ? "EN" : "中文"}
            </Button>
            <Dropdown
              menu={{
                items: [
                  {
                    key: "logout",
                    icon: <LogOut size={16} />,
                    label: <a href={logoutUrl()}>{t("logout")}</a>,
                  },
                ],
              }}
            >
              <Button type="text">
                <Space>
                  <Avatar size="small">
                    {user.name.slice(0, 1).toUpperCase()}
                  </Avatar>
                  <Typography.Text className="user-name">
                    {user.name}
                  </Typography.Text>
                </Space>
              </Button>
            </Dropdown>
          </Space>
        </Layout.Header>

        <Tabs
          className="header-tabs"
          activeKey={location.pathname}
          type="editable-card"
          hideAdd
          onChange={(path) => void navigate(path)}
          onEdit={(path, action) =>
            action === "remove" && removeTab(String(path))
          }
          items={tabs.map((tab) => ({
            key: tab.path,
            label: tab.label,
            closeIcon: <X size={13} />,
          }))}
        />

        <Layout.Content className="content" id="main-content">
          <Outlet />
        </Layout.Content>
      </Layout>
    </Layout>
  );
}
