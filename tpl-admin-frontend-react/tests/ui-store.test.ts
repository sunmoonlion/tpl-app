import { useUiStore } from "~/store/ui";

describe("ui store", () => {
  beforeEach(() => {
    useUiStore.setState({ sidebarCollapsed: false, tabs: [] });
  });

  it("deduplicates open tabs by path", () => {
    useUiStore.getState().addTab({ path: "/", label: "首页" });
    useUiStore.getState().addTab({ path: "/", label: "Home" });
    expect(useUiStore.getState().tabs).toEqual([{ path: "/", label: "首页" }]);
  });
});
