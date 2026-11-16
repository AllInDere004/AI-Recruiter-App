const { chromium, expect } = require("@playwright/test");
const assert = require("node:assert/strict");

const base = process.env.TEST_BASE_URL || "http://127.0.0.1:3000";
const email = process.env.LOCAL_E2E_EMAIL;
const password = process.env.LOCAL_E2E_PASSWORD;

async function main() {
  assert(email && password, "Synthetic local test identity is required");
  const browser = await chromium.launch({ channel: process.env.TEST_BROWSER_CHANNEL || "msedge", headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const errors = [];
  page.on("pageerror", error => errors.push(error.name));
  try {
    await page.goto(`${base}/login`);
    await page.locator("#email").fill(email);
    await page.locator('input[name="password"]').fill(password);
    await page.locator('button[type="submit"]').click();
    await page.waitForURL("**/dashboard");

    await page.goto(`${base}/jobs`);
    await expect(page.getByRole("heading", { name: "Smart job discovery" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Search Himalayas remote jobs" })).toBeEnabled();

    await page.goto(`${base}/interviews`);
    await expect(page.getByRole("heading", { name: "Interview practice" })).toBeVisible();
    await expect(page.getByLabel("Reviewed resume")).toContainText("Resume revision");

    await page.goto(`${base}/analytics`);
    await expect(page.getByRole("heading", { name: "Career analytics" })).toBeVisible();
    await expect(page.getByText("Interview practice", { exact: true })).toBeVisible();
    await expect(page.getByText(/sessions/).first()).toBeVisible();
    assert.deepEqual(errors, []);
    console.log("PASS authenticated Midnight + Solar Ember feature pages render real local-development data");
  } finally {
    await browser.close();
  }
}

main().catch(error => {
  console.error(`FAIL local activation browser check: ${error.name || "Error"}: ${String(error.message).split("\n")[0]}`);
  process.exitCode = 1;
});
