# Neon and the FastAPI app

The current frontend uses FastAPI at `http://127.0.0.1:8002`; FastAPI accesses Neon
through SQLAlchemy and psycopg2. The frontend does not query Postgres directly.
See [backend/README.md](backend/README.md) for API, model, and test instructions.

The `.neon` file links project `divine-dust-28314320`, branch `production`, in
organization `org-curly-wind-98359261`. `neon.ts` declares the infrastructure policy.
`neon deploy` pulls Neon variables into root `.env.local` (or root `.env`).
Keep shared private settings in `backend/.env`: `DATABASE_URL`,
`DATABASE_URL_UNPOOLED` (for migration scripts), `JWT_SECRET_KEY`, and `LLM_API_KEY`.
FastAPI, Next.js server configuration, and database utility scripts read this file.
Root `.env.local` and `.env` remain fallbacks; existing process environment variables
take priority. Never put database credentials or Gemini keys into a `NEXT_PUBLIC_`
variable. Restart running servers after changing settings.

## Run

```powershell
# From backend/:
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8002

# In another terminal, from the repository root:
npm install
npm run dev
```

`frontend/.env.local` must contain `NEXT_PUBLIC_API_URL=http://127.0.0.1:8002`.
For a production server, run `npm run build` and then `npm start`.
Register a FastAPI account, sign in, upload a resume, then analyze a job and generate
an email. The returned draft is already saved. Review edits use PUT; the tracker
persists status changes and supports deleting drafts. Previous demo tokens are not
valid FastAPI sessions and are cleared on authentication failure.

Existing `recruiter_*` tables, Next.js API routes, and the `test:neon` scripts belong
to the earlier Next.js-only implementation. They are not used by this frontend client.
This change does not migrate those accounts into FastAPI's `users` table.

## Verification

```powershell
# From backend/:
python -B -m unittest discover -s tests -v
```

The browser integration test uses separate local servers, a temporary SQLite database,
real PDF parsing and MiniLM embeddings, and mocked Gemini responses:

```powershell
# Terminal 1, backend/:
python -B -m tests.frontend_server

# Terminal 2, repository root:
$env:NEXT_PUBLIC_API_URL = "http://localhost:8002"
$env:NEXT_DIST_DIR = ".next-fastapi-e2e"
npm run build
npm run start -- --hostname 127.0.0.1 --port 3001

# Terminal 3, repository root:
npm run test:fastapi:browser
```

Stop the two test servers afterward. In terminal 2, remove the temporary overrides
before building or running the normal app:

```powershell
Remove-Item Env:NEXT_PUBLIC_API_URL
Remove-Item Env:NEXT_DIST_DIR
```
