import { expect, test } from "@playwright/test";

test("navigates through the Vue-aligned admin shell", async ({ page }) => {
  await page.goto("/");
  // First paint waits on the dev server's on-demand compile, so allow extra time.
  await expect(page.getByRole("heading", { name: "管理首页" })).toBeVisible({
    timeout: 45000,
  });

  // The sidebar is an Ant Design Menu, whose items expose the "menuitem" role
  // (navigation happens via onClick, not an anchor element).
  await page.getByRole("menuitem", { name: "参考页面" }).click();
  await expect(
    page.getByRole("heading", { name: "表格与操作参考页" }),
  ).toBeVisible();

  await page.getByRole("button", { name: "详情" }).first().click();
  const detail = page.getByRole("dialog");
  await expect(detail).toBeVisible();
  await expect(detail.getByText("操作详情")).toBeVisible();
});

test("provides keyboard reachable landmarks and login action", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.getByRole("main")).toBeVisible({ timeout: 30000 });
  await expect(page.getByRole("menu")).toBeVisible();
  await expect(page.getByRole("heading", { name: "管理首页" })).toBeVisible();

  await page.goto("/login");
  await expect(page.getByRole("main")).toBeVisible();
  await expect(page.getByRole("heading", { name: "欢迎回来" })).toBeVisible();
  const loginAction = page.getByRole("link", { name: "使用 Casdoor 登录" });
  await expect(loginAction).toBeVisible();
  await loginAction.focus();
  await expect(loginAction).toBeFocused();
});
