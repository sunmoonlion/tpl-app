import { create } from "zustand";
import { persist } from "zustand/middleware";

export interface OpenTab {
  path: string;
  label: string;
}

interface UiState {
  sidebarCollapsed: boolean;
  tabs: OpenTab[];
  toggleSidebar: () => void;
  addTab: (tab: OpenTab) => void;
  removeTab: (path: string) => void;
}

export const useUiStore = create<UiState>()(
  persist(
    (set) => ({
      sidebarCollapsed: false,
      tabs: [],
      toggleSidebar: () =>
        set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
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
    }),
    {
      name: "tpl-admin-ui",
      partialize: ({ sidebarCollapsed, tabs }) => ({ sidebarCollapsed, tabs }),
    },
  ),
);
