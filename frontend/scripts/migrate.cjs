const { databaseConfig } = require("../lib/server/pg-config.cjs");
const { loadEnvConfig } = require("@next/env");
const { Client } = require("pg");
const { readdirSync, readFileSync } = require("node:fs");
const { resolve } = require("node:path");
require("dotenv").config({ path: resolve(__dirname, "../../backend/.env"), quiet: true });
loadEnvConfig(resolve(__dirname, "../.."));

async function main() {
  const connectionString = process.env.DATABASE_URL_UNPOOLED;
  if (!connectionString) throw new Error("DATABASE_URL_UNPOOLED is required. Run neon deploy first.");
  const client = new Client({ ...databaseConfig(connectionString), connectionTimeoutMillis: 20000 });
  try {
    await client.connect();
    await client.query("BEGIN");
    await client.query("SELECT pg_advisory_xact_lock(193827451)");
    await client.query(`CREATE TABLE IF NOT EXISTS recruiter_migrations (
      name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now()
    )`);
    const directory = resolve(__dirname, "../db/migrations");
    for (const name of readdirSync(directory).filter(n => n.endsWith(".sql")).sort()) {
      const existing = await client.query("SELECT name FROM recruiter_migrations WHERE name = $1", [name]);
      if (existing.rowCount) { console.log(`Already applied: ${name}`); continue; }
      await client.query(readFileSync(resolve(directory, name), "utf8"));
      await client.query("INSERT INTO recruiter_migrations (name) VALUES ($1)", [name]);
      console.log(`Applied: ${name}`);
    }
    await client.query("COMMIT");
    console.log("Database migrations complete.");
  } catch (error) {
    await client.query("ROLLBACK").catch(() => {});
    throw error;
  } finally { await client.end(); }
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });
