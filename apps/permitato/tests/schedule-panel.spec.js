const { test, expect } = require("@playwright/test");
const { makeStatusPayload } = require("../../../tests/ui/helpers");

async function openPermitato(page, { permitatoStatusRoute, scheduleRoute } = {}) {
  await page.route("**/status", async (route) => {
    if (route.request().url().includes("/app/permitato/")) return route.fallback();
    await route.fulfill({ status: 200, body: JSON.stringify(makeStatusPayload()) });
  });
  if (permitatoStatusRoute) {
    await page.route("**/app/permitato/api/status", permitatoStatusRoute);
  }
  if (scheduleRoute) {
    await page.route("**/app/permitato/api/schedule", scheduleRoute);
  }
  await page.goto("/");
  await page.waitForSelector('button[data-app="permitato"]', { timeout: 5000 });
  await page.locator('button[data-app="permitato"]').click();
  await page.waitForFunction(() => {
    const badge = document.getElementById("permitatoModeValue");
    return badge && badge.textContent !== "--" && badge.textContent !== "";
  }, { timeout: 10000 });
}

const STATUS_SCHEDULED = {
  mode: "work",
  mode_display: "Work",
  mode_description: "Social media blocked",
  active_exceptions: 0,
  exceptions: [],
  pihole_available: true,
  degraded_since: null,
  client_id: "192.168.1.100",
  client_valid: true,
  schedule_active: true,
  scheduled_mode: "work",
  override_active: false,
  override_mode: null,
};

const STATUS_OVERRIDDEN = {
  ...STATUS_SCHEDULED,
  mode: "normal",
  mode_display: "Normal",
  override_active: true,
  override_mode: "normal",
};

const STATUS_NO_SCHEDULE = {
  ...STATUS_SCHEDULED,
  schedule_active: false,
  scheduled_mode: null,
};

const SCHEDULE_WITH_RULES = {
  rules: [
    { id: "r1", mode: "work", days: [0, 1, 2, 3, 4], start_time: "09:00", end_time: "17:00", enabled: true },
    { id: "r2", mode: "sfw", days: [5, 6], start_time: "22:00", end_time: "23:00", enabled: true },
  ],
  scheduled_mode: "work",
  next_transition: { time: "17:00", day: 0, mode: "normal" },
};


test("schedule toggle opens and closes panel", async ({ page }) => {
  await openPermitato(page, {
    permitatoStatusRoute: async (route) => {
      await route.fulfill({ status: 200, body: JSON.stringify(STATUS_SCHEDULED) });
    },
    scheduleRoute: async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({ status: 200, body: JSON.stringify(SCHEDULE_WITH_RULES) });
      } else {
        await route.fallback();
      }
    },
  });

  await expect(page.locator("#permitatoSchedulePanel")).toBeHidden();

  await page.locator("#permitatoScheduleToggle").click();
  await expect(page.locator("#permitatoSchedulePanel")).toBeVisible();
  await expect(page.locator(".permitato-schedule-rules li")).toHaveCount(2);

  await page.locator("#permitatoScheduleToggle").click();
  await expect(page.locator("#permitatoSchedulePanel")).toBeHidden();
});


test("schedule indicator shows scheduled when schedule is active", async ({ page }) => {
  await openPermitato(page, {
    permitatoStatusRoute: async (route) => {
      await route.fulfill({ status: 200, body: JSON.stringify(STATUS_SCHEDULED) });
    },
  });

  await expect(page.locator("#permitatoScheduleIndicator")).toBeVisible();
  await expect(page.locator("#permitatoScheduleIndicator")).toHaveText("(scheduled)");
});


test("schedule indicator shows override when overridden", async ({ page }) => {
  await openPermitato(page, {
    permitatoStatusRoute: async (route) => {
      await route.fulfill({ status: 200, body: JSON.stringify(STATUS_OVERRIDDEN) });
    },
  });

  await expect(page.locator("#permitatoScheduleIndicator")).toBeVisible();
  await expect(page.locator("#permitatoScheduleIndicator")).toHaveText("(override)");
});


test("schedule indicator hidden when no schedule", async ({ page }) => {
  await openPermitato(page, {
    permitatoStatusRoute: async (route) => {
      await route.fulfill({ status: 200, body: JSON.stringify(STATUS_NO_SCHEDULE) });
    },
  });

  await expect(page.locator("#permitatoScheduleIndicator")).toBeHidden();
});
