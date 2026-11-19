import "server-only";
import { Pool } from "pg";
import { databaseConfig } from "./pg-config.cjs";

const globalDb = globalThis as unknown as { recruiterPool?: Pool };

export function database(): Pool {
  if (!process.env.DATABASE_URL) throw new Error("DATABASE_URL is missing. Run neon deploy.");
  if (!globalDb.recruiterPool) {
    globalDb.recruiterPool = new Pool({
      ...databaseConfig(process.env.DATABASE_URL),
      max: 5,
      idleTimeoutMillis: 30000,
      connectionTimeoutMillis: 15000,
    });
    globalDb.recruiterPool.on("error", () => console.error("An idle database connection closed."));
  }
  return globalDb.recruiterPool;
}
