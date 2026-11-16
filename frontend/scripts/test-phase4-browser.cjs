const { chromium, expect: baseExpect } = require("@playwright/test");
const assert = require("node:assert/strict");
const { randomUUID } = require("node:crypto");
const { execFileSync } = require("node:child_process");
const { resolve } = require("node:path");

const expect = baseExpect.configure({ timeout: 60000 });
const base = process.env.TEST_FRONTEND_URL || "http://127.0.0.1:3001";
const allowed = new Set(["127.0.0.1", "localhost", "[::1]"]);
assert(allowed.has(new URL(base).hostname), "Phase 4 browser tests require isolated localhost fixtures.");
const python = process.env.TEST_PYTHON || resolve(__dirname, "../../.venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
const email = `phase4-browser-${randomUUID()}@example.com`;
const password = `Phase4-${randomUUID()}`;
const pdf = execFileSync(python, ["-B", "-c", "import sys,pymupdf;d=pymupdf.open();p=d.new_page();p.insert_text((72,72),'Phase Four Candidate\\nPython developer building APIs with SQL\\nSkills: Python, SQL');sys.stdout.buffer.write(d.tobytes());d.close()"]);
let stage = "launch";
let diagnostics = "";

async function main() {
  const browser = await chromium.launch({ channel: process.env.TEST_BROWSER_CHANNEL || "msedge", headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  page.setDefaultTimeout(60000);
  const errors = [], blocked = [], requests = [], failures = [];
  page.on("pageerror", error => errors.push(error.name));
  page.on("request", request => { if (request.url().includes("/api/")) requests.push(`${request.method()} ${new URL(request.url()).origin}${new URL(request.url()).pathname}`); });
  page.on("requestfailed", request => failures.push(request.failure()?.errorText || "request failed"));
  await page.route("**/api/**", route => {
    const target = new URL(route.request().url());
    if (!allowed.has(target.hostname) || target.port !== "8002") { blocked.push(target.hostname); return route.abort(); }
    return route.continue();
  });
  try {
    stage = "account and approved resume";
    await page.goto(`${base}/signup`);
    await page.locator("#email").fill(email);
    await page.locator('input[name="password"]').fill(password);
    await page.getByRole("button", { name: "Create account", exact: true }).click();
    await page.waitForURL("**/login?**");
    await page.locator('input[name="password"]').fill(password);
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await page.waitForURL("**/onboarding");
    const upload = page.waitForResponse(r => r.url().endsWith("/api/resume/upload"));
    await page.locator('input[type="file"]').setInputFiles({ name: "phase4.pdf", mimeType: "application/pdf", buffer: pdf });
    assert((await upload).ok());
    await page.getByRole("button", { name: "Save Profile", exact: true }).click();
    await page.waitForURL("**/dashboard");
    await page.goto(`${base}/profile`);
    const intelligence = page.getByRole("region", { name: "Career intelligence", exact: true });
    await intelligence.getByRole("checkbox", { name: /I reviewed the saved profile/ }).check();
    const snapshot = page.waitForResponse(r => new URL(r.url()).pathname === "/api/intelligence/resumes" && r.request().method() === "POST");
    await intelligence.getByRole("button", { name: "Save reviewed resume version", exact: true }).click();
    assert((await snapshot).ok());

    stage = "interview generation and answer";
    await page.goto(`${base}/interviews`);
    await expect(page.getByRole("heading", { name: "Interview practice", exact: true })).toBeVisible();
    await page.getByLabel("Question count").fill("1");
    const generated = page.waitForResponse(r => new URL(r.url()).pathname === "/api/interviews/sessions" && r.request().method() === "POST");
    await page.getByRole("button", { name: "Generate practice questions", exact: true }).click();
    assert((await generated).ok());
    await page.getByLabel("Answer question 1").fill("I designed a Python API, measured latency, and reduced response time by 30 percent.");
    const answer = page.waitForResponse(r => r.url().endsWith("/answer") && r.request().method() === "PUT");
    await page.getByRole("button", { name: "Save answer", exact: true }).click();
    assert((await answer).ok());

    stage = "structured feedback and history";
    const evaluated = page.waitForResponse(r => r.url().endsWith("/evaluate"));
    await page.getByRole("button", { name: "Generate structured feedback", exact: true }).click();
    assert((await evaluated).ok());
    await expect(page.getByText("Practice score: 80/100", { exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Practice history", exact: true })).toBeVisible();
    assert.deepEqual(blocked, []);
    assert.deepEqual(errors, []);
    console.log("PASS Gemini fixture generation, answer persistence, structured evaluation, and history");

    stage = "mobile interview layout";
    await page.setViewportSize({ width: 390, height: 844 });
    await page.reload();
    const size = await page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, width: window.innerWidth }));
    assert(size.scroll <= size.width + 1, "Mobile interview page must not overflow horizontally.");
    console.log("PASS mobile interview layout and isolated network boundary");
  } finally {
    diagnostics = `requests=${requests.slice(-5).join(",") || "none"}; blocked=${blocked.join(",") || "none"}; failures=${failures.slice(-3).join(",") || "none"}; pageErrors=${errors.join(",") || "none"}`;
    await browser.close();
  }
}

main().catch(error => {
  const safe = String(error?.message || "").replaceAll(email, "[synthetic-email]").replaceAll(password, "[synthetic-password]").split("\n").slice(0, 3).join(" ");
  console.error(`FAIL Phase 4 browser checks at ${stage} (${error?.name || "Error"}): ${safe}; ${diagnostics}`);
  process.exitCode = 1;
});
