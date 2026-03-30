const { test, expect } = require("@playwright/test");
const { makeStatusPayload } = require("../../../tests/ui/helpers");

async function openPermitato(page, { permitatoStatusRoute, customDomainsRoute } = {}) {
  await page.route("**/status", async (route) => {
    if (route.request().url().includes("/app/permitato/")) return route.fallback();
    await route.fulfill({ status: 200, body: JSON.stringify(makeStatusPayload()) });
  });
  if (permitatoStatusRoute) {
    await page.route("**/app/permitato/api/status", permitatoStatusRoute);
  }
  if (customDomainsRoute) {
    await page.route("**/app/permitato/api/custom-domains", customDomainsRoute);
  }
  await page.goto("/");
  await page.waitForSelector('button[data-app="permitato"]', { timeout: 5000 });
  await page.locator('button[data-app="permitato"]').click();
  await page.waitForFunction(() => {
    const badge = document.getElementById("permitatoModeValue");
    return badge && badge.textContent !== "--" && badge.textContent !== "";
  }, { timeout: 10000 });
}

const BASE_STATUS = {
  mode: "work",
  mode_display: "Work",
  mode_description: "Social media blocked",
  active_exceptions: 0,
  exceptions: [],
  pihole_available: true,
  degraded_since: null,
  client_id: "192.168.1.100",
  client_valid: true,
  schedule_active: false,
  scheduled_mode: null,
  override_active: false,
  override_mode: null,
  custom_domain_count: 2,
};

const CUSTOM_DOMAINS = {
  entries: [
    { id: "cd-1", mode: "work", domain: "example.com", regex_pattern: "(^|\\.)example\\.com$", created_at: 1700000000 },
    { id: "cd-2", mode: "sfw", domain: "adult-site.com", regex_pattern: "(^|\\.)adult-site\\.com$", created_at: 1700000100 },
  ],
};


test("custom list toggle opens and closes panel", async ({ page }) => {
  await openPermitato(page, {
    permitatoStatusRoute: async (route) => {
      await route.fulfill({ status: 200, body: JSON.stringify(BASE_STATUS) });
    },
    customDomainsRoute: async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({ status: 200, body: JSON.stringify(CUSTOM_DOMAINS) });
      } else {
        await route.fallback();
      }
    },
  });

  await expect(page.locator("#permitatoCustomListPanel")).toBeHidden();

  await page.locator("#permitatoCustomListToggle").click();
  await expect(page.locator("#permitatoCustomListPanel")).toBeVisible();

  await page.locator("#permitatoCustomListToggle").click();
  await expect(page.locator("#permitatoCustomListPanel")).toBeHidden();
});


test("panel shows domains filtered by active tab", async ({ page }) => {
  await openPermitato(page, {
    permitatoStatusRoute: async (route) => {
      await route.fulfill({ status: 200, body: JSON.stringify(BASE_STATUS) });
    },
    customDomainsRoute: async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({ status: 200, body: JSON.stringify(CUSTOM_DOMAINS) });
      } else {
        await route.fallback();
      }
    },
  });

  await page.locator("#permitatoCustomListToggle").click();
  await expect(page.locator("#permitatoCustomListPanel")).toBeVisible();

  // Default tab is Work — should show example.com
  await expect(page.locator("#permitatoCustomList li")).toHaveCount(1);
  await expect(page.locator(".custom-domain-name").first()).toHaveText("example.com");

  // Switch to SFW tab
  await page.locator('.permitato-custom-tab[data-tab="sfw"]').click();
  await expect(page.locator("#permitatoCustomList li")).toHaveCount(1);
  await expect(page.locator(".custom-domain-name").first()).toHaveText("adult-site.com");
});


test("removing a domain calls DELETE and refreshes list", async ({ page }) => {
  let removed = false;

  await openPermitato(page, {
    permitatoStatusRoute: async (route) => {
      await route.fulfill({ status: 200, body: JSON.stringify(BASE_STATUS) });
    },
    customDomainsRoute: async (route) => {
      if (route.request().method() === "GET") {
        const data = removed
          ? { entries: [CUSTOM_DOMAINS.entries[1]] }
          : CUSTOM_DOMAINS;
        await route.fulfill({ status: 200, body: JSON.stringify(data) });
      } else {
        await route.fallback();
      }
    },
  });

  await page.route("**/app/permitato/api/custom-domains/cd-1", async (route) => {
    if (route.request().method() === "DELETE") {
      removed = true;
      await route.fulfill({ status: 200, body: JSON.stringify({ deleted: true }) });
    } else {
      await route.fallback();
    }
  });

  await page.locator("#permitatoCustomListToggle").click();
  await expect(page.locator("#permitatoCustomList li")).toHaveCount(1);

  await page.locator(".custom-domain-remove-btn").first().click();

  // After remove, Work tab should be empty
  await expect(page.locator("#permitatoCustomListEmpty")).toBeVisible({ timeout: 10000 });
});
