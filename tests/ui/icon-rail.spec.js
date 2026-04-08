const { test, expect } = require("@playwright/test");
const { waitUntilReady, makeStatusPayload } = require("./helpers");

// Multi-app mock — tests that need the switcher visible use this to simulate
// two registered apps since only chat ships in core after the apps extraction.
const MULTI_APP_RESPONSE = {
  apps: [],
  ui_apps: [
    { id: "chat", name: "Potato Chat", has_ui: true, icon: "/app/chat/assets/icon.svg" },
    { id: "testapp", name: "Test App", has_ui: true, icon: "" },
  ],
};

function mockMultiApp(page) {
  return page.route("**/internal/apps", async (route) => {
    await route.fulfill({ status: 200, body: JSON.stringify(MULTI_APP_RESPONSE) });
  });
}


test("icon rail is visible and flush-left", async ({ page }) => {
  await mockMultiApp(page);
  await waitUntilReady(page);

  const rail = page.locator("#appSwitcher");
  await expect(rail).toBeVisible();

  const box = await rail.boundingBox();
  expect(box.x).toBe(0);
  expect(box.width).toBeGreaterThanOrEqual(40);
  expect(box.width).toBeLessThanOrEqual(56);
});


test("active app button has active class", async ({ page }) => {
  await mockMultiApp(page);
  await waitUntilReady(page);

  const chatBtn = page.locator('button[data-app="chat"]');
  await expect(chatBtn).toHaveClass(/active/);
});


test("clicking switcher button changes active indicator", async ({ page }) => {
  await mockMultiApp(page);
  await waitUntilReady(page);

  const testBtn = page.locator('button[data-app="testapp"]');
  await testBtn.click();
  await expect(testBtn).toHaveClass(/active/);
  await expect(page.locator('button[data-app="chat"]')).not.toHaveClass(/active/);
});


test("icon rail is to the left of the sidebar", async ({ page }) => {
  await mockMultiApp(page);
  await waitUntilReady(page);

  const railBox = await page.locator("#appSwitcher").boundingBox();
  const sidebarBox = await page.locator("#sidebarPanel").boundingBox();

  expect(railBox.x + railBox.width).toBeLessThanOrEqual(sidebarBox.x + 1);
});


test("switcher buttons have title tooltip with app name", async ({ page }) => {
  await mockMultiApp(page);
  await waitUntilReady(page);

  const chatBtn = page.locator('button[data-app="chat"]');
  const title = await chatBtn.getAttribute("title");
  expect(title).toBeTruthy();
  expect(title.toLowerCase()).toContain("chat");
});


test("sidebar keeps fixed width when icon rail is hidden (single-app)", async ({ page }) => {
  // Mock /internal/apps to return only chat — switcher will be hidden
  await page.route("**/internal/apps", async (route) => {
    await route.fulfill({
      status: 200,
      body: JSON.stringify({
        apps: [],
        ui_apps: [{ id: "chat", name: "Potato Chat", has_ui: true, icon: "/app/chat/assets/icon.svg" }],
      }),
    });
  });

  await waitUntilReady(page);

  // Rail should be hidden
  await expect(page.locator("#appSwitcher")).toBeHidden();

  // Sidebar must stay in the fixed-width track, not expand
  const sidebarWidth = await page.locator("#sidebarPanel").evaluate(el => el.getBoundingClientRect().width);
  expect(sidebarWidth).toBeLessThan(500);

  // Main content must get the majority of the viewport
  const mainWidth = await page.locator(".chat-shell").evaluate(el => el.getBoundingClientRect().width);
  expect(mainWidth).toBeGreaterThan(sidebarWidth);
});
