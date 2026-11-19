const { chromium, expect } = require("@playwright/test");
const assert = require("node:assert/strict");
const { randomUUID } = require("node:crypto");
const base = process.env.TEST_BASE_URL || "http://127.0.0.1:3000";
async function main() {
  const browser = await chromium.launch({ channel: process.env.TEST_BROWSER_CHANNEL || "msedge", headless: true });
  const page = await browser.newPage();
  page.setDefaultTimeout(30000);
  let token;
  const email = `neon-browser-${randomUUID()}@example.com`;
  const password = `Neon-browser-${randomUUID()}`;
  const company = `Browser Test ${Date.now()}`;
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  try {
    await page.goto(`${base}/signup`);
    await page.locator("#name").fill("Neon Browser Test");
    await page.locator("#email").fill(email);
    await page.locator('input[name="password"]').fill(password);
    const signup = page.waitForResponse(r => r.url().endsWith("/api/auth/register") && r.request().method() === "POST");
    await page.locator('button[type="submit"]').click();
    const signupResponse = await signup;
    assert.equal(signupResponse.status(), 201);
    await page.waitForURL("**/onboarding");
    token = await page.evaluate(() => localStorage.getItem("ai_recruiter_token"));
    console.log("PASS browser signup creates an authenticated Neon-backed account");
    await page.getByRole("button", { name: /fill profile manually/i }).click();
    await page.getByPlaceholder("e.g. Docker, PostgreSQL, Next.js...").fill("TypeScript");
    await page.getByRole("button", { name: "Add Skill" }).click();
    await expect(page.getByText("TypeScript", { exact: true }).first()).toBeVisible();
    const save = page.waitForResponse(r => r.url().endsWith("/api/profile") && r.request().method() === "PUT");
    await page.getByRole("button", { name: "Save Profile" }).click();
    assert.equal((await save).status(), 200);
    await page.waitForURL("**/dashboard");
    await page.goto(`${base}/profile`);
    await expect(page.getByPlaceholder("e.g. Sarah Connor")).toHaveValue("Neon Browser Test");
    await expect(page.getByText("TypeScript", { exact: true }).first()).toBeVisible();
    console.log("PASS browser onboarding saves profile and reloads it from Neon");
    await page.goto(`${base}/new-email`);
    await page.getByPlaceholder("e.g. Stripe, Linear, Google").fill(company);
    await page.getByPlaceholder("e.g. Junior Software Engineer").fill("Software Engineer");
    await page.getByPlaceholder("Paste the requirements, qualifications, and role description here...").fill("Build accessible applications with TypeScript and PostgreSQL.");
    const jobSave = page.waitForResponse(r => r.url().endsWith("/api/jobs/analyze") && r.request().method() === "POST");
    await page.getByRole("button", { name: "Analyze & Extract Needs" }).click();
    assert.equal((await jobSave).status(), 201);
    await page.getByRole("button", { name: "Proceed to Situation" }).click();
    await page.getByRole("button", { name: "Compute Matching Points" }).click();
    await page.getByRole("button", { name: "Generate Factual Recruiter Email" }).click();
    const draftSave = page.waitForResponse(r => r.url().endsWith("/api/drafts") && r.request().method() === "POST");
    await page.getByRole("button", { name: "Save to Tracker" }).click();
    assert.equal((await draftSave).status(), 201);
    await page.waitForURL("**/tracker");
    await expect(page.getByText(company, { exact: true }).first()).toBeVisible();
    const advance = page.waitForResponse(r => /\/api\/drafts\/[^/]+$/.test(r.url()) && r.request().method() === "PATCH");
    await page.getByTitle("Advance to Sent").first().click();
    assert.equal((await advance).status(), 200);
    await page.reload();
    await expect(page.getByText(company, { exact: true }).first()).toBeVisible();
    await expect(page.getByTitle("Advance to Replied").first()).toBeVisible();
    console.log("PASS browser job-to-draft workflow, tracker status update, and persistence after reload");
    // Clear all client state: logging in must recover the saved profile and tracker from Postgres.
    await page.evaluate(() => localStorage.clear());
    await page.goto(`${base}/login`);
    await page.locator("#email").fill(email);
    await page.locator('input[name="password"]').fill(password);
    await page.locator('button[type="submit"]').click();
    await page.waitForURL("**/dashboard");
    token = await page.evaluate(() => localStorage.getItem("ai_recruiter_token"));
    await page.goto(`${base}/profile`);
    await expect(page.getByPlaceholder("e.g. Sarah Connor")).toHaveValue("Neon Browser Test");
    await expect(page.getByText("TypeScript", { exact: true }).first()).toBeVisible();
    await page.goto(`${base}/tracker`);
    await expect(page.getByText(company, { exact: true }).first()).toBeVisible();
    await expect(page.getByTitle("Advance to Replied").first()).toBeVisible();
    assert.deepEqual(errors, []);
    console.log("PASS fresh login recovers Neon data after localStorage is erased; no browser runtime errors");
    console.log("All Neon browser checks passed.");
  } finally {
    if (!token) {
      const login = await fetch(`${base}/api/auth/login`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email, password }),
      }).catch(() => null);
      if (login?.ok) token = (await login.json()).access_token;
    }
    if (token) {
      const cleanup = await fetch(`${base}/api/me`, { method: "DELETE", headers: { Authorization: `Bearer ${token}` } });
      assert.equal(cleanup.status, 200, "Browser test account cleanup failed");
      console.log("Removed browser test account and its data.");
    }
    await browser.close();
  }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
