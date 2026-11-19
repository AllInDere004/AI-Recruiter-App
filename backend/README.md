# FastAPI backend

Run commands from this directory:

```powershell
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8002
```

Keep your backend settings in `backend/.env`. Set `DATABASE_URL`, `JWT_SECRET_KEY`, and
`LLM_API_KEY` (your Google Gemini API key). `LLM_MODEL` defaults to
`gemini-2.5-flash` and can be changed to a model available to your account.
The backend resolves this file relative to its source directory, so it works from
any working directory. Root `.env` and `.env.local` provide fallback values;
`backend/.env` overrides them, and process environment variables take priority.
Restart the backend after changing environment settings.
Either `LLM_API_KEY` or `GEMINI_API_KEY` configures the Gemini client;
`LLM_API_KEY` takes priority when both names exist in the same settings source.
Settings are loaded once at process startup; restart Uvicorn after editing `.env`.
Never commit `.env` or send API keys in browser requests.

## Resume and profile routes

Authenticate with `POST /api/auth/login` using JSON `{ "email": "...", "password": "..." }`.
Pass the returned JWT as `Authorization: Bearer <access_token>` to:

- `POST /api/resume/upload`: multipart form field `file`, content type `application/pdf`.
- `GET /api/profile/me`: retrieve your saved profile.
- `PUT /api/profile/me`: JSON containing `full_name`, `parsed_data`, or both.

Uploads accept text-based PDFs up to 10 MB. Encrypted, malformed, empty, or scanned
PDFs without extractable text return a clear error; OCR is not performed. A successful
upload extracts text in memory, asks Gemini for JSON, validates it, then creates or
updates the signed-in user's profile. Failed parsing or Gemini calls do not overwrite
saved data. Re-uploading updates the same profile record.

Manual edits preserve omitted fields. Explicit null clears an optional field.
`parsed_data`, when supplied, replaces the saved dictionary. Profile reads and edits
return 404 until the user has uploaded a resume. A missing Gemini API key returns 503;
provider or invalid-response errors return 502.

## Tests

```powershell
python -m pip install -r requirements-dev.txt
python -B -m unittest discover -s tests -v
```

Tests use isolated in-memory databases and real generated PDFs. Gemini is mocked at
the SDK boundary; no live API key or production database writes are needed.

## Job analysis and matching

- `POST /api/jobs/analyze`: JSON with `description` and optional `title`/`company`.
  Gemini extracts required skills and responsibilities; explicit title/company values
  take priority over extracted values. The response and saved `extracted_skills`
  dictionary include the analyzed title, company, required skills, and responsibilities.
- `GET /api/jobs/`: list only the signed-in user's saved jobs, newest first.
- `POST /api/match/compare`: JSON `{ "job_id": 1 }`. Requires the user's saved resume
  and an owned job. Returns `overall_score`, `matched_skills`, `missing_skills`, and
  an explanatory summary.

Matching uses `sentence-transformers/all-MiniLM-L6-v2`, loaded lazily on the first
comparison. The first request may download model weights into the Hugging Face cache;
subsequent comparisons reuse the model. An unavailable model returns 503, without
substituting a fake score. Network access is needed if the weights are not cached.
MiniLM truncates inputs to its supported token length; scores reflect that model limit.

The overall score is 0-100: 70% nonnegative cosine similarity and 30% required-skill
coverage. If no required skills are listed, semantic similarity alone determines the
score. Skill matching ignores case, whitespace, and duplicate requirements, and
preserves the displayed names from the job. It does not guess skill aliases.

Job analysis requires the Gemini key configured above. Semantic matching runs locally
and does not send resume text to Gemini. These are similarity and coverage measures,
not calibrated hiring probabilities. Routes enforce job and profile ownership.

## Email generation and draft tracker

- `POST /api/email/generate`: JSON with an owned `job_id`, `situation`, `tone`, and
  optional `custom_notes`. Supported situation templates are `apply`, `cold_email`,
  `follow_up`, `thank_you`, `referral`, and `reply_recruiter`; other values or missing
  template files use a standard prompt.
- `GET /api/drafts/`: list the signed-in user's drafts, newest first.
- `GET /api/drafts/{draft_id}`: retrieve an owned draft.
- `PUT /api/drafts/{draft_id}`: edit `subject_line`, `body`, `situation`, or `tone`.
  Omitted fields are preserved. A null subject is allowed; supplied body, situation,
  and tone must be nonempty. Changing the body clears the old `match_score`, since
  that score describes the generated body, not the manually edited text.
- `DELETE /api/drafts/{draft_id}`: remove an owned draft (204 with no response body).

Generation makes two Gemini calls: one to generate validated JSON with a subject and
body, and one to identify candidate claims unsupported by the raw resume. Warnings
are returned with the generated draft, including the subject in factual review.
Warnings identify unverified claims, not proven falsehoods, and are advisory rather
than a guarantee of factual correctness. They are returned by generation and are not
stored in the Draft table. Notes and job requirements are not proof of past candidate
achievements. Generation, verification, or scoring failures do not save a partial draft.

The 0-100 score weights semantic alignment 75% and key phrase coverage 25%.
Semantic alignment weights the job-to-email cosine similarity 60% and the
resume-to-email similarity 40%, clamping negative similarities to zero. Phrase
coverage uses job content words and two-word phrases, excluding stop words.
It is an alignment heuristic, not a hiring probability or factual verification result.
If no key phrases remain, semantic alignment alone determines the score.

The test suite covers this workflow with isolated databases, mocked Gemini responses,
and deterministic embedding vectors; the standalone real-model check verifies the
MiniLM embedding path separately.

## Next.js integration

The frontend uses `NEXT_PUBLIC_API_URL=http://127.0.0.1:8002` in
`frontend/.env.local`, and calls the FastAPI `/api/...` endpoints directly.
Bearer JWTs are stored under `ai_recruiter_token`; registration returns a user and
redirects to sign-in, while login obtains a token and fetches `/api/auth/me`.
No sample accounts, mock data, client-generated scores, or local-storage persistence
fallbacks are used. A new user uploads a resume to create a profile before editing it.

The tracker persists `Draft`, `Sent`, `Replied`, `Interview`, and `Rejected` in the
backend `drafts.status` column. Startup adds this column to older tables with a
`Draft` default and preserves existing records. Tracker edits use PUT and deletions
use DELETE; the browser joins owned jobs onto drafts for display. Generation already
saves a draft, so the review page updates that record rather than creating a duplicate.
The older Next.js `/api` implementation is not used by this frontend client.

Run the frontend with `npm run dev` from the repository root. Restart Next.js after
changing `NEXT_PUBLIC_API_URL` (rebuild when using a production server).

## Phase 2 career intelligence

See [the implementation/test report](../PHASE2_REPORT.md) and
[development migration verification](../PHASE2_MIGRATION_TEST.md).
The additive SQL proposal is in `migrations/002_career_intelligence.sql`.
Ordinary PostgreSQL startup performs no schema creation or alteration.

`ENABLE_CAREER_INTELLIGENCE` defaults to false. Do not enable it on production
until the migration has a verified backup/restore checkpoint and explicit approval.
Existing profile, job, matching, email, draft and tracker routes continue working
without the new tables. The older root `db:migrate` command manages recruiter tables
and does not apply the new FastAPI migration.

All new routes are authenticated under `/api/intelligence`: status, reviewed
resume snapshots, saved reports, document versions, and approved PDF/DOCX exports.
Scoring uses deterministic source evidence, not the LLM. Original resume text
remains unchanged by tailoring; history and downloads stay private.
The optional development test server uses temporary SQLite and mocked Gemini.
See the report for its isolated startup commands and both browser test commands.

`AI_REQUESTS_PER_MINUTE` defaults to 30 for existing Gemini-backed routes.
`CAREER_AI_REQUESTS_PER_MINUTE` defaults to 6 for new AI document/guidance requests.

## Phase 3 job discovery and applications

Phase 3 is feature-gated and requires both reviewed migrations in order:

1. `migrations/002_career_intelligence.sql`
2. `migrations/003_smart_job_discovery.sql`

Application startup never executes either migration. Keep the feature disabled until
both migrations have passed on a Neon development branch and production activation has
a verified backup/restore checkpoint plus explicit approval.

Server-side environment variable names (store values only in the existing ignored
`.env` files; never expose them through `NEXT_PUBLIC_*` variables):

```dotenv
ENABLE_JOB_DISCOVERY=false
JOB_PROVIDER=himalayas
HIMALAYAS_API_KEY=
HIMALAYAS_API_BASE_URL=https://himalayas.app/jobs/api
JOB_SEARCH_REQUESTS_PER_MINUTE=10
JOB_IMPORT_REQUESTS_PER_MINUTE=5
JOB_PROVIDER_TIMEOUT_SECONDS=12
JOB_IMPORT_MAX_BYTES=2000000
REMINDER_WORKER_TOKEN=
```

Himalayas is the default live-search provider. The upstream public API permits
anonymous access, but this application requires `HIMALAYAS_API_KEY` so it never relies
on the shared anonymous allowance. The key is sent only from the backend as a Bearer
token. An absent key produces an explicit provider-not-configured response; it never
enables fixtures as live jobs. The legacy Jooble adapter remains available only when
an existing deployment explicitly selects `JOB_PROVIDER=jooble` and supplies its
existing Jooble settings.

The durable reminder worker contract is:

```text
POST /api/applications/internal/process-reminders
X-Reminder-Worker-Token: <REMINDER_WORKER_TOKEN>
```

The token must be a long random server-side value. Configure an existing hosting cron
to call the endpoint over HTTPS. No cron, queue, Neon Function, email provider, or paid
service is deployed automatically. Authenticated users also process their own due
in-app reminders when loading the tracker/dashboard; this improves UX but is not a
substitute for the durable deployment trigger.
Limits are per authenticated user and server process; multiple application
instances need shared quota enforcement. Neither setting changes provider billing.

## Phase 4 advanced features

Migration `migrations/004_advanced_features.sql` is additive and must follow `002`
and `003`. `ENABLE_ADVANCED_FEATURES` defaults to false. Interview practice,
notification preferences, Gmail integration, advanced analytics, and administration
remain unavailable until the migration is reviewed and the feature is enabled for
that environment. Application startup never applies the migration.

Runtime configuration names are `ENVIRONMENT`, `CORS_ORIGINS`, `ALLOWED_HOSTS`,
`FORCE_HTTPS`, `ENABLE_ADVANCED_FEATURES`, `INTERVIEW_AI_REQUESTS_PER_MINUTE`, and
`INTERVIEW_MAX_ANSWER_CHARS`. Optional Gmail names are `ENABLE_GMAIL`,
`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_OAUTH_REDIRECT_URI`,
`GMAIL_TOKEN_ENCRYPTION_KEY`, and `OAUTH_STATE_TTL_MINUTES`. Keep all values in the
server-side secret store; none belong in a `NEXT_PUBLIC_*` variable.

Production startup validates HTTPS, explicit origins/hosts, PostgreSQL, a strong JWT
key, and complete Gmail settings when Gmail is enabled. Use `/live` for process
liveness and `/ready` for database readiness. See `../DEPLOYMENT.md` and
`../PRODUCTION_READINESS.md` before promoting an environment.
