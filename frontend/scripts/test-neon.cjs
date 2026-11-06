const { databaseConfig } = require("../lib/server/pg-config.cjs");
const assert = require("node:assert/strict");
const { randomUUID } = require("node:crypto");
const { Client } = require("pg");
const { loadEnvConfig } = require("@next/env");
const { resolve } = require("node:path");
require("dotenv").config({ path: resolve(__dirname, "../../backend/.env"), quiet: true });
loadEnvConfig(resolve(__dirname, "../.."));
const base = process.env.TEST_BASE_URL || "http://localhost:3000";
const accounts = [];
const password = `Neon-test-${randomUUID()}`;
async function api(path, { token, method = "GET", data, status = 200 } = {}) {
  const response = await fetch(`${base}/api${path}`, {
    method, headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    ...(data !== undefined ? { body: JSON.stringify(data) } : {}),
  });
  const body = await response.json();
  assert.equal(response.status, status, `${method} ${path}: ${JSON.stringify(body)}`);
  return body;
}
async function main() {
  const db = new Client({ ...databaseConfig(process.env.DATABASE_URL_UNPOOLED), connectionTimeoutMillis: 20000 });
  try {
    const home = await fetch(base);
    assert.equal(home.status, 200);
    const health = await api("/health");
    assert.equal(health.services.postgres, "connected");
    console.log("PASS production homepage and Postgres health endpoint");
    for (let i = 0; i < 2; i++) {
      const email = `neon-e2e-${randomUUID()}@example.com`;
      const account = await api("/auth/register", { method: "POST", data: { name: `Neon Test ${i}`, email, password }, status: 201 });
      accounts.push(account);
    }
    const first = accounts[0];
    const other = accounts[1];
    const token = first.access_token;
    await api("/auth/register", { method: "POST", data: { name: "Duplicate", email: first.user.email, password }, status: 409 });
    await api("/auth/login", { method: "POST", data: { email: first.user.email, password: "incorrect-password" }, status: 401 });
    const login = await api("/auth/login", { method: "POST", data: { email: first.user.email, password } });
    assert.equal(login.user.id, first.user.id);
    const me = await api("/me", { token: login.access_token });
    assert.equal(me.email, first.user.email);
    console.log("PASS persisted registration, login, session authentication, duplicate and invalid-password rejection");
    await api("/profile", { status: 401 });
    await api("/profile", { token: "mock-jwt-token-verified", status: 401 });
    const original = await api("/profile", { token });
    assert.deepEqual(original.data_json.skills, []);
    const profile = { ...original.data_json, name: "Neon Persistence Test", skills: ["TypeScript", "PostgreSQL"], projects: [{ title: "Neon app", description: "Database integration", tech: ["PostgreSQL"] }] };
    await api("/profile", { token, method: "PUT", data: { data_json: profile } });
    const saved = await api("/profile", { token: login.access_token });
    assert.equal(saved.data_json.name, profile.name);
    assert.deepEqual(saved.data_json.skills, profile.skills);
    assert.equal((await api("/me", { token })).name, profile.name);
    console.log("PASS profile write/read through independent sessions and account synchronization");
    const job = await api("/jobs/analyze", { token, method: "POST", data: { company: "Neon Test", role: "Engineer", raw_text: "Build with TypeScript and PostgreSQL" }, status: 201 });
    assert(job.extracted_json.required_skills.includes("TypeScript"));
    assert((await api("/jobs", { token })).some(row => row.id === job.id));
    assert.equal((await api(`/jobs/${job.id}`, { token })).company, "Neon Test");
    const draft = await api("/drafts", { token, method: "POST", status: 201, data: {
      id: `neon-test-${randomUUID()}`, job_id: job.id, situation: "apply", tone: "formal",
      subject: "Neon integration test", body: "Persist this draft in Postgres.", score: 90,
      score_breakdown: { overall: 90 }, status: "Draft", version: 1,
    } });
    await api(`/drafts/${draft.id}`, { token, method: "PATCH", data: { status: "Interview", body: "Updated and persisted." } });
    const reread = await api(`/drafts/${draft.id}`, { token: login.access_token });
    assert.equal(reread.status, "Interview");
    assert.equal(reread.body, "Updated and persisted.");
    assert((await api("/drafts", { token })).some(row => row.id === draft.id && row.status === "Interview"));
    console.log("PASS job creation and draft save, update, tracker list, and independent-session reload");
    await api(`/jobs/${job.id}`, { token: other.access_token, status: 404 });
    await api(`/drafts/${draft.id}`, { token: other.access_token, status: 404 });
    await api(`/drafts/${draft.id}`, { token: other.access_token, method: "PATCH", data: { status: "Rejected" }, status: 404 });
    assert.deepEqual(await api("/drafts", { token: other.access_token }), []);
    console.log("PASS cross-account read/write isolation and anonymous access rejection");
    await db.connect();
    const proof = await db.query(`SELECT u.password_hash, p.data_json->>'name' AS name,
      d.data_json->>'status' AS status FROM recruiter_users u JOIN recruiter_profiles p ON p.user_id = u.id
      JOIN recruiter_drafts d ON d.user_id = u.id WHERE u.id = $1 AND d.id = $2`, [first.user.id, draft.id]);
    assert.equal(proof.rows[0].name, profile.name);
    assert.equal(proof.rows[0].status, "Interview");
    assert(!proof.rows[0].password_hash.includes(password));
    assert.match(proof.rows[0].password_hash, /^[0-9a-f]{32}:[0-9a-f]{128}$/);
    console.log("PASS direct Neon SQL independently confirms API writes and hashed password storage");
    await api("/auth/logout", { token: login.access_token, method: "POST", data: {} });
    await api("/me", { token: login.access_token, status: 401 });
    console.log("PASS server-side session revocation");
    for (const account of accounts) {
      await api("/me", { token: account.access_token, method: "DELETE" });
      await api("/me", { token: account.access_token, status: 401 });
    }
    for (const table of ["recruiter_users", "recruiter_sessions", "recruiter_profiles", "recruiter_jobs", "recruiter_drafts"]) {
      const column = table === "recruiter_users" ? "id" : "user_id";
      const result = await db.query(`SELECT count(*)::int AS count FROM ${table} WHERE ${column} = ANY($1::uuid[])`, [accounts.map(a => a.user.id)]);
      assert.equal(result.rows[0].count, 0);
    }
    console.log("PASS account deletion cascades; all test records removed");
    console.log("All Neon end-to-end checks passed.");
  } finally {
    for (const account of accounts) {
      await fetch(`${base}/api/me`, { method: "DELETE", headers: { Authorization: `Bearer ${account.access_token}` } }).catch(() => {});
    }
    await db.end().catch(() => {});
  }
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });
