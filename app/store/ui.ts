import { create } from "zustand";
import { persist } from "zustand/middleware";

export interface OpenTab {
  path: string;
  label: string;
}

export type ThemeMode = "light" | "dark" | "system";

interface UiState {
  sidebarCollapsed: boolean;
  mobileMenuOpen: boolean;
  tabs: OpenTab[];
  themeMode: ThemeMode;
  themeColor: string;
  showTabs: boolean;
  showBreadcrumb: boolean;
  toggleSidebar: () => void;
  setMobileMenuOpen: (open: boolean) => void;
  addTab: (tab: OpenTab) => void;
  removeTab: (path: string) => void;
  setThemeMode: (mode: ThemeMode) => void;
  setThemeColor: (color: string) => void;
  setShowTabs: (visible: boolean) => void;
  setShowBreadcrumb: (visible: boolean) => void;
}

export const useUiStore = create<UiState>()(
  persist(
    (set) => ({
      sidebarCollapsed: false,
      mobileMenuOpen: false,
      tabs: [],
      themeMode: "light",
      themeColor: "#1677ff",
      showTabs: true,
      showBreadcrumb: true,
      toggleSidebar: () =>
        set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
      setMobileMenuOpen: (open) => set({ mobileMenuOpen: open }),
      addTab: (tab) =>
        set((state) =>
          state.tabs.some((item) => item.path === tab.path)
            ? state
            : { tabs: [...state.tabs, tab] },
        ),
      removeTab: (path) =>
        set((state) => ({
          tabs: state.tabs.filter((item) => item.path !== path),
        })),
      setThemeMode: (mode) => set({ themeMode: mode }),
      setThemeColor: (color) => set({ themeColor: color }),
      setShowTabs: (visible) => set({ showTabs: visible }),
      setShowBreadcrumb: (visible) => set({ showBreadcrumb: visible }),
    }),
    {
      name: "tpl-admin-ui",
      partialize: ({
        sidebarCollapsed,
        tabs,
        themeMode,
        themeColor,
        showTabs,
        showBreadcrumb,
      }) => ({
        sidebarCollapsed,
        tabs,
        themeMode,
        themeColor,
        showTabs,
        showBreadcrumb,
      }),
    },
  ),
);
