import { NextRequest, NextResponse } from "next/server";
import { randomBytes, randomUUID, scrypt, createHash, timingSafeEqual } from "node:crypto";
import { promisify } from "node:util";
import { z } from "zod";
import { database } from "@/lib/server/db";
import type { PoolClient } from "pg";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
const deriveKey = promisify(scrypt);
const hashToken = (value: string) => createHash("sha256").update(value).digest("hex");
const emptyProfile = (name: string, email: string) => ({
  name, email, education: [], skills: [], projects: [], experience: [], achievements: [],
});
const credentials = z.object({ email: z.string().trim().email().max(254).transform(v => v.toLowerCase()), password: z.string().min(6).max(256) });
const profileSchema = z.object({
  name: z.string().trim().min(1).max(200), email: z.string().email().max(254),
  phone: z.string().max(100).optional(), location: z.string().max(300).optional(),
  headline: z.string().max(500).optional(), summary: z.string().max(20000).optional(),
  education: z.array(z.object({ institution: z.string(), degree: z.string(), field_of_study: z.string(), graduation_year: z.string(), gpa: z.string().optional() })).max(100),
  skills: z.array(z.string().max(200)).max(200),
  projects: z.array(z.object({ title: z.string(), description: z.string(), tech: z.array(z.string()), link: z.string().optional() })).max(100),
  experience: z.array(z.object({ company: z.string(), role: z.string(), duration: z.string(), description: z.array(z.string()) })).max(100),
  achievements: z.array(z.string()).max(100),
});
const draftFields = z.object({
  job_id: z.string().min(1).max(200),
  situation: z.enum(["apply", "cold_email", "follow_up", "thank_you", "referral", "career_switcher", "recruiter_reply"]),
  tone: z.enum(["formal", "friendly", "confident", "short"]),
  subject: z.string().max(1000), body: z.string().max(100000), score: z.number().min(0).max(100),
  score_breakdown: z.record(z.string(), z.unknown()),
  status: z.enum(["Draft", "Sent", "Replied", "Interview", "Rejected"]),
  version: z.number().int().min(1), parent_draft_id: z.string().nullable().optional(),
  sent_at: z.string().datetime().nullable().optional(), follow_up_due: z.boolean().optional(),
  matching_points: z.array(z.record(z.string(), z.unknown())).optional(),
  hallucination_check: z.record(z.string(), z.unknown()).optional(),
});
class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}
const json = (value: unknown, status = 200) => NextResponse.json(value, { status, headers: { "Cache-Control": "no-store" } });
async function readBody(request: NextRequest) {
  const text = await request.text();
  if (Buffer.byteLength(text) > 1024 * 1024) throw new ApiError(413, "Request is too large.");
  try { return JSON.parse(text); } catch { throw new ApiError(400, "Invalid JSON."); }
}
async function passwordHash(password: string, salt = randomBytes(16).toString("hex")) {
  const key = await deriveKey(password, salt, 64) as Buffer;
  return `${salt}:${key.toString("hex")}`;
}
async function createSession(client: PoolClient, userId: string) {
  const token = randomBytes(32).toString("base64url");
  await client.query("DELETE FROM recruiter_sessions WHERE user_id = $1 AND expires_at <= now()", [userId]);
  await client.query("INSERT INTO recruiter_sessions (token_hash, user_id, expires_at) VALUES ($1, $2, now() + interval '7 days')", [hashToken(token), userId]);
  return token;
}
async function authenticated(request: NextRequest) {
  const token = request.headers.get("authorization")?.match(/^Bearer (.+)$/i)?.[1];
  if (!token) throw new ApiError(401, "Please sign in.");
  const result = await database().query(`SELECT u.id, u.name, u.email, u.created_at
    FROM recruiter_users u JOIN recruiter_sessions s ON s.user_id = u.id
    WHERE s.token_hash = $1 AND s.expires_at > now()`, [hashToken(token)]);
  if (!result.rows[0]) throw new ApiError(401, "Session expired. Please sign in again.");
  return result.rows[0];
}
async function handle(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  try {
    const { path: segments } = await params;
    const path = segments.join("/");
    const method = request.method;
    if (path === "health" && method === "GET") {
      await database().query("SELECT 1");
      return json({ status: "ok", services: { postgres: "connected" } });
    }
    if ((path === "auth/register" || path === "auth/login") && method === "POST") {
      const body = await readBody(request);
      const parsed = credentials.parse(body);
      const client = await database().connect();
      try {
        await client.query("BEGIN");
        let user;
        if (path === "auth/register") {
          const { name } = z.object({ name: z.string().trim().min(1).max(200) }).parse(body);
          const hashed = await passwordHash(parsed.password);
          const result = await client.query(`INSERT INTO recruiter_users (id, name, email, password_hash)
            VALUES ($1, $2, $3, $4) RETURNING id, name, email, created_at`, [randomUUID(), name, parsed.email, hashed]);
          user = result.rows[0];
          await client.query("INSERT INTO recruiter_profiles (user_id, data_json) VALUES ($1, $2)", [user.id, JSON.stringify(emptyProfile(name, parsed.email))]);
        } else {
          const result = await client.query("SELECT id, name, email, created_at, password_hash FROM recruiter_users WHERE email = $1", [parsed.email]);
          const row = result.rows[0];
          // Also perform the expensive hash for unknown accounts.
          const stored = row?.password_hash || `${"0".repeat(32)}:${"0".repeat(128)}`;
          const calculated = await passwordHash(parsed.password, stored.split(":")[0]);
          if (!row || !timingSafeEqual(Buffer.from(stored), Buffer.from(calculated))) throw new ApiError(401, "Invalid email or password.");
          const { password_hash: _, ...publicUser } = row;
          user = publicUser;
        }
        const token = await createSession(client, user.id);
        await client.query("COMMIT");
        return json({ access_token: token, token_type: "bearer", user }, path === "auth/register" ? 201 : 200);
      } catch (error) { await client.query("ROLLBACK"); throw error; }
      finally { client.release(); }
    }
    const user = await authenticated(request);
    if (path === "auth/logout" && method === "POST") {
      const token = request.headers.get("authorization")!.slice(7);
      await database().query("DELETE FROM recruiter_sessions WHERE token_hash = $1", [hashToken(token)]);
      return json({ success: true });
    }
    if (path === "me") {
      if (method === "GET") return json(user);
      if (method === "DELETE") {
        await database().query("DELETE FROM recruiter_users WHERE id = $1", [user.id]);
        return json({ success: true, message: "All user data deleted successfully." });
      }
    }
    if (path === "profile") {
      if (method === "GET") {
        const result = await database().query("SELECT user_id, data_json, updated_at FROM recruiter_profiles WHERE user_id = $1", [user.id]);
        return json(result.rows[0]);
      }
      if (method === "PUT") {
        const { data_json } = z.object({ data_json: profileSchema }).parse(await readBody(request));
        const client = await database().connect();
        try {
          await client.query("BEGIN");
          await client.query("UPDATE recruiter_users SET name = $1, email = $2 WHERE id = $3", [data_json.name, data_json.email.toLowerCase(), user.id]);
          data_json.email = data_json.email.toLowerCase();
          const result = await client.query("UPDATE recruiter_profiles SET data_json = $1, updated_at = now() WHERE user_id = $2 RETURNING user_id, data_json, updated_at", [JSON.stringify(data_json), user.id]);
          await client.query("COMMIT");
          return json(result.rows[0]);
        } catch (error) { await client.query("ROLLBACK"); throw error; }
        finally { client.release(); }
      }
    }
    if (path === "jobs/analyze" && method === "POST") {
      const body = z.object({ company: z.string().trim().max(300).optional(), role: z.string().trim().max(300).optional(), raw_text: z.string().max(100000).optional() }).parse(await readBody(request));
      const company = body.company || "Unspecified company";
      const role = body.role || "Unspecified role";
      const raw = body.raw_text || "";
      const keywords = ["Python", "FastAPI", "React", "Next.js", "TypeScript", "JavaScript", "PostgreSQL", "SQL", "Docker", "AWS", "Git", "REST APIs", "Tailwind"];
      const job = { id: randomUUID(), user_id: user.id, company, role, raw_text: raw,
        extracted_json: { company_name: company, role_title: role, required_skills: keywords.filter(k => raw.toLowerCase().includes(k.toLowerCase())), responsibilities: [], tone_hints: [] },
        created_at: new Date().toISOString() };
      await database().query("INSERT INTO recruiter_jobs (id, user_id, data_json) VALUES ($1, $2, $3)", [job.id, user.id, JSON.stringify(job)]);
      return json(job, 201);
    }
    if (path === "jobs" && method === "GET") {
      const result = await database().query("SELECT data_json FROM recruiter_jobs WHERE user_id = $1 ORDER BY created_at DESC LIMIT 500", [user.id]);
      return json(result.rows.map(row => row.data_json));
    }
    if (segments[0] === "jobs" && segments.length === 2 && method === "GET") {
      const result = await database().query("SELECT data_json FROM recruiter_jobs WHERE id = $1 AND user_id = $2", [segments[1], user.id]);
      if (!result.rows[0]) throw new ApiError(404, "Job not found.");
      return json(result.rows[0].data_json);
    }
    if (path === "drafts" && method === "GET") {
      const result = await database().query("SELECT d.data_json || jsonb_build_object('job', j.data_json) AS data_json FROM recruiter_drafts d JOIN recruiter_jobs j ON j.id = d.job_id AND j.user_id = d.user_id WHERE d.user_id = $1 ORDER BY d.updated_at DESC LIMIT 500", [user.id]);
      return json(result.rows.map(row => row.data_json));
    }
    if (path === "drafts" && method === "POST") {
      const input = await readBody(request);
      const fields = draftFields.parse(input);
      const { id } = z.object({ id: z.string().min(1).max(200) }).parse(input);
      const job = await database().query("SELECT data_json FROM recruiter_jobs WHERE id = $1 AND user_id = $2", [fields.job_id, user.id]);
      if (!job.rows[0]) throw new ApiError(404, "Job not found.");
      const now = new Date().toISOString();
      const draft = { ...fields, id, user_id: user.id, job: job.rows[0].data_json, created_at: now, updated_at: now };
      const result = await database().query(`INSERT INTO recruiter_drafts (id, user_id, job_id, data_json)
        VALUES ($1, $2, $3, $4) ON CONFLICT (id) DO UPDATE
        SET data_json = EXCLUDED.data_json || jsonb_build_object('created_at', recruiter_drafts.data_json->'created_at'), job_id = EXCLUDED.job_id, updated_at = now()
        WHERE recruiter_drafts.user_id = EXCLUDED.user_id RETURNING data_json`, [id, user.id, fields.job_id, JSON.stringify(draft)]);
      if (!result.rows[0]) throw new ApiError(409, "Draft ID is already in use.");
      return json(result.rows[0].data_json, 201);
    }
    if (segments[0] === "drafts" && segments.length === 2) {
      const id = segments[1];
      const found = await database().query("SELECT d.data_json || jsonb_build_object('job', j.data_json) AS data_json FROM recruiter_drafts d JOIN recruiter_jobs j ON j.id = d.job_id AND j.user_id = d.user_id WHERE d.id = $1 AND d.user_id = $2", [id, user.id]);
      if (!found.rows[0]) throw new ApiError(404, "Draft not found.");
      if (method === "GET") return json(found.rows[0].data_json);
      if (method === "PATCH") {
        // Only user-editable fields may be patched; identity and job ownership stay fixed.
        const patch = draftFields.omit({ job_id: true, parent_draft_id: true }).partial().parse(await readBody(request));
        const updatedAt = new Date().toISOString();
        const result = await database().query(`UPDATE recruiter_drafts SET data_json = data_json || $1::jsonb, updated_at = now() WHERE id = $2 AND user_id = $3 RETURNING data_json`, [JSON.stringify({ ...patch, updated_at: updatedAt }), id, user.id]);
        if (!result.rows[0]) throw new ApiError(404, "Draft not found.");
        return json(result.rows[0].data_json);
      }
    }
    throw new ApiError(404, "Endpoint not found.");
  } catch (error) {
    if (error instanceof ApiError) return json({ detail: error.message }, error.status);
    if (error instanceof z.ZodError) return json({ detail: error.issues.map(i => `${i.path.join(".")}: ${i.message}`).join("; ") }, 400);
    if ((error as { code?: string }).code === "23505") return json({ detail: "That email is already registered." }, 409);
    console.error("API request failed", { code: (error as { code?: string }).code || "unknown" });
    return json({ detail: "The database request failed. Please try again." }, 503);
  }
}
export { handle as GET, handle as POST, handle as PUT, handle as PATCH, handle as DELETE };
