# AI Recruiter App

AI Recruiter is a full-stack career workspace for resume intelligence, job discovery,
application tracking, interview practice, and career analytics. The application keeps
the existing Midnight + Solar Ember interface while using authenticated, user-owned
data throughout its FastAPI and Neon PostgreSQL backend.

## Features

- Secure registration, login, profiles, and per-user data isolation
- PDF resume parsing and profile extraction with Google Gemini
- Resume-to-job analysis, matching, and tailored career documents
- Live Himalayas job discovery with filters, pagination, bookmarks, and imports
- Application tracking, reminders, and notification preferences
- Technical, HR, behavioral, and project-based interview practice
- Gemini-generated interview questions, feedback, scores, and history
- Career funnel, application, and interview analytics backed by PostgreSQL data
- Server-authorized administration and optional, disabled-by-default Gmail OAuth

## Technology stack

- **Frontend:** Next.js 14, React 18, TypeScript, Tailwind CSS, TanStack Query,
  Recharts, GSAP, and Playwright
- **Backend:** FastAPI, Pydantic, SQLAlchemy, PyJWT, Google Generative AI, and pytest
- **Database:** Neon PostgreSQL with reviewed additive SQL migrations
- **External services:** Google Gemini and Himalayas Jobs API
- **Automation:** GitHub Actions for tests, lint, type checking, build, dependency
  auditing, and secret checks

## Local setup

### Prerequisites

- Python 3.12+
- Node.js 20+ and npm
- A Neon development-branch PostgreSQL connection (do not use production locally)
- Google Gemini and Himalayas API credentials

### 1. Configure the backend

```powershell
Copy-Item .env.example backend/.env
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
```

Edit `backend/.env` with your own values. At minimum, configure `DATABASE_URL`,
`JWT_SECRET_KEY`, `LLM_API_KEY`, `LLM_MODEL`, and `HIMALAYAS_API_KEY`. The local
environment files are ignored by Git. Keep feature flags disabled until migrations
`002`, `003`, and `004` exist on the selected non-production database branch.

Start FastAPI on the local development address:

```powershell
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8002
```

Backend API: `http://127.0.0.1:8002`
OpenAPI docs: `http://127.0.0.1:8002/docs`

### 2. Configure the frontend

In another terminal:

```powershell
Copy-Item frontend/.env.example frontend/.env.local
cd frontend
npm ci
npm run dev -- --hostname 127.0.0.1 --port 3000
```

Frontend: `http://localhost:3000`

## Environment variables

The safe templates document every supported setting without credentials:

- [Backend template](.env.example): database, authentication, Gemini, Himalayas,
  feature flags, request limits, and optional Gmail OAuth names
- [Frontend template](frontend/.env.example): local public API base URL only

Never place API keys, JWT secrets, OAuth client secrets, or database credentials in a
`NEXT_PUBLIC_*` variable. See [backend/README.md](backend/README.md) for route and
feature details and [DEPLOYMENT.md](DEPLOYMENT.md) for staging guidance.

## Database migrations

The backend does not automatically apply the Phase 2-4 migrations:

1. `backend/migrations/002_career_intelligence.sql`
2. `backend/migrations/003_smart_job_discovery.sql`
3. `backend/migrations/004_advanced_features.sql`

Use a Neon development branch and the documented verification process. Never run
migrations against production without a verified backup, rehearsal, and explicit
approval.

## Quality checks

```powershell
cd backend
python -m pytest tests -q

cd ..\frontend
npm run lint
npx tsc --noEmit --incremental false
npm run build
```

The test suite uses isolated test databases and mocked provider calls unless a script
explicitly states that it is an integration test.

## Screenshots

Add current product screenshots here before publishing a release. Do not include user
resumes, email addresses, API credentials, database details, or other private data.

![AI Recruiter visual theme](frontend/public/images/recruiter-sunset-hero.png)

## Security

- Environment files, private keys, local databases, caches, and build artifacts are
  excluded from source control.
- Authentication and ownership checks are enforced server-side.
- Gmail integration and advanced features remain opt-in through environment flags.
- Report vulnerabilities privately; do not open a public issue containing secrets.

## License

No license has been declared. All rights are reserved unless the repository owner adds
a license file.
