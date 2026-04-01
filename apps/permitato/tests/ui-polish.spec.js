const { test, expect } = require("@playwright/test");
const { waitUntilReady, makeStatusPayload } = require("../../../tests/ui/helpers");

const NOW = Math.floor(Date.now() / 1000);

async function openPermitato(page, { permitatoStatusRoute } = {}) {
  await page.route("**/status", async (route) => {
    if (route.request().url().includes("/app/permitato/")) return route.fallback();
    await route.fulfill({ status: 200, body: JSON.stringify(makeStatusPayload()) });
  });
  if (permitatoStatusRoute) {
    await page.route("**/app/permitato/api/status", permitatoStatusRoute);
  }
  await page.goto("/");
  await page.waitForSelector('button[data-app="permitato"]', { timeout: 5000 });
  await page.locator('button[data-app="permitato"]').click();
  await page.waitForFunction(() => {
    const badge = document.getElementById("permitatoModeValue");
    return badge && badge.textContent !== "--" && badge.textContent !== "";
  }, { timeout: 10000 });
}

const WORK_STATUS = {
  mode: "work",
  mode_display: "Work",
  mode_description: "Social media blocked",
  active_exceptions: 1,
  exceptions: [
    { id: "exc-1", domain: "twitter.com", reason: "check DMs", granted_at: NOW - 600, expires_at: NOW + 2400, ttl_seconds: 3600 },
  ],
  pihole_available: true,
  degraded_since: null,
  client_id: "192.168.1.100",
  client_valid: true,
  blocking_bypassed: false,
  schedule_active: false,
  scheduled_mode: null,
  override_active: false,
  override_mode: null,
  custom_domain_count: 0,
};


test("mode switch shows pulse animation on badge", async ({ page }) => {
  let currentMode = "work";

  await page.route("**/app/permitato/api/mode", async (route) => {
    const body = JSON.parse(route.request().postData());
    currentMode = body.mode;
    await route.fulfill({ status: 200, body: JSON.stringify({ mode: currentMode, mode_display: currentMode.charAt(0).toUpperCase() + currentMode.slice(1) }) });
  });

  await openPermitato(page, {
    permitatoStatusRoute: async (route) => {
      await route.fulfill({ status: 200, body: JSON.stringify({
        ...WORK_STATUS,
        mode: currentMode,
        mode_display: currentMode.charAt(0).toUpperCase() + currentMode.slice(1),
      }) });
    },
  });

  // Switch to normal mode
  await page.locator('.permitato-mode-btn[data-mode="normal"]').click();

  // Badge should get the pulse animation class
  await expect(page.locator("#permitatoModeValue")).toHaveClass(/mode-changed/, { timeout: 5000 });
});


test("active app persists across page reload", async ({ page }) => {
  await page.route("**/status", async (route) => {
    if (route.request().url().includes("/app/permitato/")) return route.fallback();
    await route.fulfill({ status: 200, body: JSON.stringify(makeStatusPayload()) });
  });
  await page.route("**/app/permitato/api/status", async (route) => {
    await route.fulfill({ status: 200, body: JSON.stringify(WORK_STATUS) });
  });

  await page.goto("/");
  await page.waitForSelector('button[data-app="permitato"]', { timeout: 5000 });

  // Switch to Permitato
  await page.locator('button[data-app="permitato"]').click();
  await page.waitForFunction(() => {
    const badge = document.getElementById("permitatoModeValue");
    return badge && badge.textContent !== "--" && badge.textContent !== "";
  }, { timeout: 10000 });

  // Verify Permitato is active
  await expect(page.locator('button[data-app="permitato"]')).toHaveClass(/active/);

  // Reload — should return to Permitato, not Chat
  await page.reload();
  await page.waitForFunction(() => {
    const badge = document.getElementById("permitatoModeValue");
    return badge && badge.textContent !== "--" && badge.textContent !== "";
  }, { timeout: 10000 });

  await expect(page.locator('button[data-app="permitato"]')).toHaveClass(/active/);
});


test("revoke button enters confirm state before firing DELETE", async ({ page }) => {
  let deleteCount = 0;

  await openPermitato(page, {
    permitatoStatusRoute: async (route) => {
      await route.fulfill({ status: 200, body: JSON.stringify(WORK_STATUS) });
    },
  });

  await page.route("**/app/permitato/api/exceptions/exc-1", async (route) => {
    if (route.request().method() === "DELETE") {
      deleteCount++;
      await route.fulfill({ status: 200, body: JSON.stringify({ revoked: true }) });
    } else {
      await route.fallback();
    }
  });

  // Open exceptions panel
  await page.locator("#permitatoExceptionsToggle").click();
  await expect(page.locator("#permitatoExceptionsList li")).toHaveCount(1);

  const btn = page.locator(".exc-revoke-btn").first();

  // First click — should show "Sure?" but NOT fire DELETE
  await btn.click();
  await expect(btn).toHaveText("Sure?");
  await expect(btn).toHaveClass(/confirm-pending/);
  expect(deleteCount).toBe(0);

  // Second click — should fire DELETE
  await btn.click();
  expect(deleteCount).toBe(1);
});


test("confirm state reverts after timeout", async ({ page }) => {
  await openPermitato(page, {
    permitatoStatusRoute: async (route) => {
      await route.fulfill({ status: 200, body: JSON.stringify(WORK_STATUS) });
    },
  });

  // Open exceptions panel
  await page.locator("#permitatoExceptionsToggle").click();
  await expect(page.locator("#permitatoExceptionsList li")).toHaveCount(1);

  const btn = page.locator(".exc-revoke-btn").first();

  // Click to enter confirm state
  await btn.click();
  await expect(btn).toHaveText("Sure?");

  // Wait for timeout to revert (3s + buffer)
  await expect(btn).toHaveText("Revoke", { timeout: 5000 });
  await expect(btn).not.toHaveClass(/confirm-pending/);
});
