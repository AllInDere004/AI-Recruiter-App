import dotenv from "dotenv";
import { fileURLToPath } from "node:url";

// Load shared server settings without overriding runtime or frontend variables.
dotenv.config({ path: fileURLToPath(new URL("../backend/.env", import.meta.url)), quiet: true });
dotenv.config({ path: fileURLToPath(new URL("../.env.local", import.meta.url)), quiet: true });
dotenv.config({ path: fileURLToPath(new URL("../.env", import.meta.url)), quiet: true });

export default { distDir: process.env.NEXT_DIST_DIR || ".next" };
