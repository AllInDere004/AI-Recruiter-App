const { chromium, expect: baseExpect } = require("@playwright/test");
const assert = require("node:assert/strict");
const { randomUUID } = require("node:crypto");
const { execFileSync } = require("node:child_process");
const { readFileSync } = require("node:fs");
const { resolve } = require("node:path");
const expect = baseExpect.configure({ timeout: 60000 });
const base = process.env.TEST_FRONTEND_URL || "http://127.0.0.1:3001";
const localHosts = new Set(["localhost", "127.0.0.1", "[::1]"]);
assert(localHosts.has(new URL(base).hostname), "Career smoke tests require an isolated local frontend.");
const python = process.env.TEST_PYTHON || resolve(__dirname, "../../.venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
const email = `career-browser-${randomUUID()}@example.com`;
const password = `Career-test-${randomUUID()}`;
const pdf = execFileSync(python, ["-B", "-c", "import sys,pymupdf;d=pymupdf.open();p=d.new_page();p.insert_text((72,72),'Frontend Test\\ncandidate@example.com\\nPython developer building APIs with SQL\\nSkills: Python, SQL\\nEducation: Computer Science');sys.stdout.buffer.write(d.tobytes());d.close()"]);
let stage = "launch";

const isApi = (response, path, method = "POST") =>
  new URL(response.url()).pathname === path && response.request().method() === method;
const mustSucceed = response => assert(response.ok(), "Expected an isolated API request to succeed.");

async function login(page) {
  await page.goto(`${base}/login`);
  await page.locator("#email").fill(email);
  await page.locator('input[name="password"]').fill(password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.waitForURL("**/dashboard");
}

async function main() {
  const browser = await chromium.launch({ channel: process.env.TEST_BROWSER_CHANNEL || "msedge", headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  page.setDefaultTimeout(60000);
  const pageErrors = [];
  const blockedDestinations = [];
  page.on("pageerror", error => pageErrors.push(error.name));
  // Prevent a misconfigured frontend from sending any test writes to production.
  await page.route("**/api/**", route => {
    const target = new URL(route.request().url());
    if (!localHosts.has(target.hostname) || target.port !== "8002") {
      blockedDestinations.push(true);
      return route.abort();
    }
    return route.continue();
  });
  try {
    stage = "signup and profile upload";
    await page.goto(`${base}/signup`);
    await page.locator("#email").fill(email);
    await page.locator('input[name="password"]').fill(password);
    await page.getByRole("button", { name: "Create account", exact: true }).click();
    await page.waitForURL("**/login?**");
    await page.locator('input[name="password"]').fill(password);
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await page.waitForURL("**/onboarding");
    const upload = page.waitForResponse(response => isApi(response, "/api/resume/upload"));
    await page.locator('input[type="file"]').setInputFiles({ name: "synthetic-career.pdf", mimeType: "application/pdf", buffer: pdf });
    mustSucceed(await upload);
    await expect(page.getByRole("textbox", { name: "Full name", exact: true })).toHaveValue("Frontend Test");
    await page.getByRole("button", { name: "Save Profile", exact: true }).click();
    await page.waitForURL("**/dashboard");
    console.log("PASS isolated signup, PDF extraction, profile review, and save");

    stage = "reviewed resume version and ATS report";
    await page.goto(`${base}/profile`);
    const profileIntelligence = page.getByRole("region", { name: "Career intelligence", exact: true });
    await expect(profileIntelligence).toBeVisible();
    await profileIntelligence.getByRole("checkbox", { name: /I reviewed the saved profile/ }).check();
    const snapshot = page.waitForResponse(response => isApi(response, "/api/intelligence/resumes"));
    await profileIntelligence.getByRole("button", { name: "Save reviewed resume version", exact: true }).click();
    const snapshotResponse = await snapshot; mustSucceed(snapshotResponse);
    const resume = await snapshotResponse.json();
    assert.equal(resume.approved, true);
    assert.equal(typeof resume.id, "number");
    const ats = page.waitForResponse(response => isApi(response, "/api/intelligence/analyze"));
    await profileIntelligence.getByRole("button", { name: "Analyze ATS readiness", exact: true }).click();
    const atsResponse = await ats; mustSucceed(atsResponse);
    const atsReport = await atsResponse.json();
    assert.equal(atsReport.resume_version_id, resume.id);
    await expect(profileIntelligence.getByRole("heading", { name: "ATS readiness", exact: true })).toBeVisible();
    console.log("PASS reviewed immutable resume version and persisted ATS analysis");

    stage = "job analysis and deterministic matching";
    await page.goto(`${base}/new-email`);
    await page.getByRole("textbox", { name: "Company", exact: true }).fill("Integration Labs");
    await page.getByRole("textbox", { name: "Role title", exact: true }).fill("Backend Engineer");
    await page.getByRole("textbox", { name: "Job description", exact: true }).fill("Backend Engineer at Integration Labs. Build Python APIs with SQL and Docker.");
    const analyze = page.waitForResponse(response => isApi(response, "/api/jobs/analyze"));
    await page.getByRole("button", { name: "Analyze & Extract Needs", exact: true }).click();
    const analyzedResponse = await analyze; mustSucceed(analyzedResponse);
    const job = await analyzedResponse.json();
    const intelligence = page.getByRole("region", { name: "Career intelligence", exact: true });
    await expect(intelligence.getByRole("combobox", { name: "Resume version for analysis", exact: true })).toHaveValue(String(resume.id));
    await intelligence.getByRole("checkbox", { name: /Include AI learning guidance/ }).check();
    const match = page.waitForResponse(response => isApi(response, "/api/intelligence/analyze"));
    await intelligence.getByRole("button", { name: "Analyze career match", exact: true }).click();
    const matchResponse = await match; mustSucceed(matchResponse);
    const report = await matchResponse.json();
    assert.equal(report.job_id, job.id);
    assert.equal(typeof report.result.overall_score, "number");
    assert(report.result.gaps.some(gap => gap.skill === "Docker"));
    assert(report.result.gap_explanation);
    await expect(intelligence.getByRole("heading", { name: "Explainable compatibility", exact: true })).toBeVisible();
    await expect(intelligence.getByRole("heading", { name: "Skill gaps and practical next steps", exact: true })).toBeVisible();
    await expect(intelligence.getByRole("heading", { name: "ATS readiness", exact: true })).toBeVisible();
    await page.reload();
    await page.getByRole("combobox", { name: "Saved jobs", exact: true }).selectOption(String(job.id));
    await expect(intelligence.getByRole("combobox", { name: "Saved career analysis", exact: true })).toHaveValue(String(report.id));
    console.log("PASS source-backed match, weighted categories, required gap, ATS, learning guidance, and reload");

    stage = "cover letter generation and immutable edits";
    await page.getByRole("combobox", { name: "Career document type", exact: true }).selectOption("cover_letter");
    const generate = page.waitForResponse(response => isApi(response, "/api/intelligence/documents/generate"));
    await page.getByRole("button", { name: "Generate career document", exact: true }).click();
    const generatedResponse = await generate; mustSucceed(generatedResponse);
    const original = await generatedResponse.json();
    assert.equal(original.kind, "cover_letter");
    assert.equal(original.approved, false);
    await expect(page.getByRole("button", { name: "Download PDF", exact: true })).toBeDisabled();
    const originalBody = await page.getByRole("textbox", { name: "Career document content", exact: true }).inputValue();
    await page.getByRole("textbox", { name: "Career document content", exact: true }).fill(originalBody + "\n\nThank you for your time.");
    const edit = page.waitForResponse(response => isApi(response, `/api/intelligence/documents/${original.id}`, "PUT"));
    await page.getByRole("button", { name: "Save document as new version", exact: true }).click();
    const editedResponse = await edit; mustSucceed(editedResponse);
    const edited = await editedResponse.json();
    assert.notEqual(edited.id, original.id);
    assert.equal(edited.parent_id, original.id);
    const regenerate = page.waitForResponse(response => isApi(response, "/api/intelligence/documents/generate"));
    await page.getByRole("button", { name: "Regenerate as new version", exact: true }).click();
    const regeneratedResponse = await regenerate; mustSucceed(regeneratedResponse);
    const regenerated = await regeneratedResponse.json();
    assert.equal(regenerated.parent_id, edited.id);
    assert(regenerated.revision > edited.revision);
    await page.getByRole("checkbox", { name: /I reviewed this document/ }).check();
    const approval = page.waitForResponse(response => isApi(response, `/api/intelligence/documents/${regenerated.id}`, "PUT"));
    await page.getByRole("button", { name: "Approve reviewed document", exact: true }).click();
    const approvedResponse = await approval; mustSucceed(approvedResponse);
    assert.equal((await approvedResponse.json()).approved, true);
    console.log("PASS cover letter generation, immutable edits, regeneration lineage, and explicit approval");

    stage = "authorized readable exports";
    for (const format of ["pdf", "docx"]) {
      const downloadEvent = page.waitForEvent("download");
      await page.getByRole("button", { name: `Download ${format.toUpperCase()}`, exact: true }).click();
      const download = await downloadEvent;
      const buffer = readFileSync(await download.path());
      assert(buffer.length > 100);
      if (format === "pdf") {
        assert(buffer.subarray(0, 5).equals(Buffer.from("%PDF-")));
        execFileSync(python, ["-B", "-c", "import sys,pymupdf;d=pymupdf.open(stream=sys.stdin.buffer.read(),filetype='pdf');assert len(d)>0;assert any(p.get_text().strip() for p in d)"], { input: buffer });
      } else {
        assert(buffer.subarray(0, 2).equals(Buffer.from("PK")));
        execFileSync(python, ["-B", "-c", "import sys,io,zipfile,xml.etree.ElementTree as E;z=zipfile.ZipFile(io.BytesIO(sys.stdin.buffer.read()));r=E.fromstring(z.read('word/document.xml'));assert ''.join(r.itertext()).strip()"], { input: buffer });
      }
    }
    console.log("PASS authenticated PDF and DOCX downloads with readable document content");

    stage = "tailored resume comparison and version history";
    await page.getByRole("combobox", { name: "Career document type", exact: true }).selectOption("tailored_resume");
    const tailor = page.waitForResponse(response => isApi(response, "/api/intelligence/documents/generate"));
    await page.getByRole("button", { name: "Generate career document", exact: true }).click();
    const tailoredResponse = await tailor; mustSucceed(tailoredResponse);
    const tailored = await tailoredResponse.json();
    assert.equal(tailored.kind, "tailored_resume");
    await expect(page.getByRole("heading", { name: "Original resume for this version", exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Tailored draft", exact: true })).toBeVisible();
    await expect(page.getByLabel("Original resume source", { exact: true })).toContainText("Python developer building APIs with SQL");
    await expect(page.getByRole("combobox", { name: "Saved document versions", exact: true }).locator("option")).toHaveCount(4);
    await page.reload();
    await page.getByRole("combobox", { name: "Saved jobs", exact: true }).selectOption(String(job.id));
    await expect(page.getByRole("combobox", { name: "Saved document versions", exact: true }).locator("option")).toHaveCount(4);
    console.log("PASS tailored original/draft comparison and immutable version history after refresh");

    stage = "re-login persistence and dashboard";
    await page.getByTitle("Logout").click();
    await page.waitForURL("**/login");
    await login(page);
    await expect(page.getByRole("heading", { name: "Saved career intelligence", exact: true })).toBeVisible();
    await page.goto(`${base}/new-email?job_id=${job.id}`);
    await expect(page.getByRole("combobox", { name: "Saved document versions", exact: true }).locator("option")).toHaveCount(4);
    await expect(page.getByRole("combobox", { name: "Saved career analysis", exact: true })).toHaveValue(String(report.id));
    await page.getByRole("combobox", { name: "Saved document versions", exact: true }).selectOption(String(regenerated.id));
    await expect(page.getByRole("button", { name: "Download PDF", exact: true })).toBeEnabled();
    assert.equal(blockedDestinations.length, 0, "No API call may target a non-test backend.");
    assert.equal(pageErrors.length, 0, "No browser runtime errors expected.");
    console.log("PASS saved reports, reviewed versions, and approved documents across re-login; no browser runtime errors");
    stage = "mobile layout and reachable controls";
    await page.setViewportSize({ width: 390, height: 844 });
    await page.reload();
    await expect(page.getByRole("combobox", { name: "Saved document versions", exact: true }).locator("option")).toHaveCount(4);
    await expect(page.getByRole("combobox", { name: "Saved career analysis", exact: true })).toHaveValue(String(report.id));
    await page.getByRole("combobox", { name: "Saved document versions", exact: true }).selectOption(String(regenerated.id));
    const exportButton = page.getByRole("button", { name: "Download PDF", exact: true });
    await exportButton.scrollIntoViewIfNeeded();
    await expect(exportButton).toBeEnabled();
    await expect(exportButton).toBeInViewport();
    const dimensions = await page.evaluate(() => ({ scrollWidth: document.documentElement.scrollWidth, viewportWidth: window.innerWidth }));
    assert(dimensions.scrollWidth <= dimensions.viewportWidth + 1, "Mobile document panels must fit the viewport without horizontal page overflow.");
    if (process.env.TEST_SCREENSHOT === "1") await page.screenshot({ path: resolve(__dirname, "../preview-phase2-mobile.png"), fullPage: true });
    console.log("PASS mobile390 layout, persisted job/document panels, and reachable export controls");
    console.log("All isolated Phase 2 career browser checks passed.");
  } finally { await browser.close(); }
}

main().catch(error => {
  // Framework error objects can include form values; never print them.
  console.error(`FAIL career browser checks at ${stage} (${error?.name || "Error"})`);
  process.exitCode = 1;
});
