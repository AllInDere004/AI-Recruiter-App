# Phase 1 — Stage 1 audit and baseline

Audit date: 2026-11-06 (Asia/Calcutta).

## Status and scope

Stage 1 is complete. This report records the existing application before significant implementation, as requested. No application behavior, UI, credentials, production records, schema, cloud plan, or paid service has been changed. Stage 2–7 implementation is not yet complete.

The workspace initially had no Git repository. A local Git repository was initialized; source baseline commit `8c42636` was created on `main`, then branch `feature/phase-1-core-reliability` was created. The baseline preserves the pre-existing application, including prior configuration fixes. An explicit source allowlist excluded environment files, virtual environments, caches, logs, generated outputs, preview images, and local skills. A credential-pattern scan of selected text sources passed before the baseline commit. This is a source baseline, not a database backup.

Only audit documentation and Git-ignore safeguards are new tracked-work candidates at this checkpoint. Next.js added generated output paths to `frontend/tsconfig.json` during verification; those audit-only additions were removed afterward. Existing local artifacts and the user's development servers were preserved.

## Architecture discovered

| Area | Actual implementation |
| --- | --- |
| Frontend | Next.js 14.2.35 App Router, React 18, TypeScript strict mode |
| Styling and interaction | Tailwind, GSAP, existing shared UI components, dnd-kit, Recharts |
| Package management | npm; root scripts delegate to `frontend/`; root/frontend lockfiles |
| Current API | FastAPI, Pydantic, SQLAlchemy, psycopg2 |
| Current authentication | passlib/bcrypt password hashing; python-jose HS256 bearer JWT; 30-minute expiry; browser localStorage token |
| Database | Neon PostgreSQL, database `neondb`, branch `production` |
| AI | Google `google-genai`, configured `gemini-2.5-flash`, explicit API `v1beta` |
| Resume extraction | PyMuPDF, in-memory PDF extraction, 10 MB limit |
| Semantic matching | sentence-transformers, lazily loaded local MiniLM |
| Second API implementation | Reachable Next.js catch-all API; node-postgres, scrypt passwords, opaque sessions, recruiter-prefixed tables |

Environment loading: absolute root `.env`, then root `.env.local`, then `backend/.env`; later files override earlier files and process environment takes priority. The current API client uses `NEXT_PUBLIC_API_URL` for FastAPI. Private database and Gemini settings stay server-side. Both `LLM_API_KEY` and `GEMINI_API_KEY` are accepted; `LLM_API_KEY` wins when both are in the same source. No key or connection string is included in this report.

## Page → API → table map

| Page / module | Current routes | Tables |
| --- | --- | --- |
| Landing `/` | Static marketing | None |
| Signup / login | `/api/auth/register`, `/api/auth/login`, `/api/auth/me` | users |
| Onboarding / profile | `/api/resume/upload`, GET/PUT `/api/profile/me` | profiles |
| Dashboard | GET `/api/drafts/`, `/api/jobs/`, `/api/profile/me` | drafts, jobs, profiles |
| Outreach studio | Profile/jobs reads, `/api/jobs/analyze`, `/api/match/compare`, `/api/email/generate`, draft PUT | profiles, jobs, drafts |
| Tracker | Jobs/drafts reads; draft PUT/DELETE | jobs, drafts |
| Draft details | Draft GET/PUT/DELETE; regeneration via email API | drafts, jobs, profiles |
| Settings | `/api/auth/me`; browser sign-out | users |
| Health | `/health` | SELECT 1 |

No separate saved-jobs page or dedicated cover-letter generation route was found. Saved jobs are used inside the outreach flow. Marketing mentions cover letters, but the verified existing workflow generates email templates; this audit does not claim dedicated cover-letter coverage.

## Baseline verification actually executed

| Check | Command / method | Result |
| --- | --- | --- |
| Backend unit/integration/auth/ownership/AI suites | From backend: `..\\.venv\\Scripts\\python.exe -B -m unittest discover -s tests -v` | **81 passed** |
| Frontend types | From frontend: `npx tsc --noEmit --incremental false` | **Passed** |
| Production build | Root: `NEXT_DIST_DIR=.next-phase1-baseline npm run build` (PowerShell environment assignment) | **Passed**, all 12 static pages generated |
| Lint | Root: `CI=1 npm run lint` (PowerShell environment assignment) | **Failed to run**, exit 1: ESLint is not configured; Next opens interactive setup |
| Browser end-to-end | Root: `npm run test:fastapi:browser`, project virtualenv prepended to PATH | **Passed** |
| Neon connectivity | Existing SQLAlchemy/psycopg2 client; read-only transaction, SELECT 1 | **Passed** |
| Production identity / SSL | Neon CLI metadata + client TLS inspection | **Passed**: production ready/default, compute active, host matches, neondb, TLS 1.3 |
| Confirmed validation disclosure | Synthetic rejected signup, no lifespan/DB access; checked marker presence only | **Defect reproduced**: submitted password echoed in default 422 response |
| Live Gemini generation in this audit | Not executed | Mocked in current suites; previous conversation's live success is not counted as a new audit run |

Versions observed: Node 24.21.0, npm 11.19.0, Python 3.14.8. No dependencies were installed or updated during this audit.

Browser isolation used the existing `backend/tests/frontend_server.py` on port 8002, temporary SQLite, and a mocked Gemini SDK boundary. A separate Next dev server on port 3001 used `NEXT_PUBLIC_API_URL=http://127.0.0.1:8002` and `NEXT_DIST_DIR=.next-phase1-e2e`. The existing app on ports 3000/8001 was not restarted. The test servers were stopped after the run.

Browser checks passed: signup/login contract, incorrect-password feedback, new-user onboarding, PDF failure/success, review/save/refresh of profile, job-analysis failure/success, semantic matching, generation warnings, saved-draft editing, tracker status persistence, detail edits, deletion after reload, expired-session handling, logout and re-login. No browser runtime errors were reported.

This verifies the existing workflow with isolated persistence and mocked AI, not a production-data write-through or a new live Gemini run. The suite exercises owned Bearer requests; cross-user rejection is verified by backend tests. It does not establish arbitrary request-race safety.

Legacy `test:neon` and `test:neon:browser` were **not run**: they target the duplicate Next API and create/delete records, so existing defaults are unsafe for this production audit.

## Read-only database and migration assessment

The existing production endpoint matches the configured URL. SSL options are `sslmode=require` and `channel_binding=require`; the client session uses TLS 1.3. All audit queries used read-only transactions. No startup lifespan or migration runner was invoked against production.

| Table | Column summary | Ownership and existing indexes |
| --- | --- | --- |
| users | integer id; email; hashed_password; is_active; created_at | PK id; unique indexed email; redundant id index |
| profiles | integer id/user_id; full_name; raw_resume_text; parsed_data JSON; updated_at | Unique non-null user FK → users; PK and id index |
| jobs | integer id/user_id; title; company; description; extracted_skills JSON; created_at | User FK → users; PK, id/title/company indexes; no owner-history index |
| drafts | integer id/user_id/job_id; situation; tone; subject_line; body; match_score; created_at/updated_at; status | User/job FKs; PK, id/situation indexes; no owner-history/job index or status CHECK |
| recruiter_users | UUID id; name; email; password_hash; created_at | PK id; unique email |
| recruiter_profiles | UUID user_id; data_json JSONB; updated_at | PK/user FK → recruiter_users |
| recruiter_jobs | text id; UUID user_id; data_json JSONB; created_at | PK, owner FK, owner/created_at index |
| recruiter_drafts | text id/job_id; UUID user_id; data_json JSONB; created_at/updated_at | PK, owner/job FKs, owner/updated_at index |
| recruiter_sessions | token_hash; UUID user_id; expires_at | PK, owner FK, owner index |
| recruiter_migrations | name; applied_at | PK name; records `001_recruiter.sql` |

All listed foreign keys cascade on deletion. FastAPI owns the four unprefixed tables; these contain current application records. Recruiter data/session tables are currently empty; the migration-history table contains its original migration record. No record contents were read or disclosed.

Both table families independently reference a draft's owner and job; neither has a composite FK enforcing that the job belongs to that owner. No existing draft/job ownership mismatches or invalid FastAPI tracker statuses were found. Routes currently enforce ownership in application code.

Migration tooling diverges: `frontend/db/migrations/001_recruiter.sql` manages recruiter tables, while FastAPI uses startup metadata creation and an ad hoc draft-status alteration.

**Proposals only, not executable migrations or approved operations:**

1. Version explicit FastAPI migrations; make ordinary production startup perform no DDL.
2. Add owner/created_at/id indexes to active jobs/drafts and an index for drafts.job_id, after representative query-plan checks.
3. Consider parent uniqueness on (id,user_id) plus a composite draft (job_id,user_id) foreign key, preserving both table families.
4. Add a tracker-status CHECK for Draft, Sent, Replied, Interview, Rejected.
5. Assess pagination for jobs/drafts histories and redundant indexes separately.

Any migration must first be tested on a Neon development branch. Production requires an exact reviewed proposal, verified backup/restore procedure, and explicit approval. No branch, backup, or production schema operation was created/executed during Stage 1.

## Prioritized findings and risks

### Highest priority

1. **Implicit production DDL at startup.** `backend/app/main.py` calls `Base.metadata.create_all` and `ensure_draft_status_column`. The latter can issue ALTER TABLE. Current production has the status column, but the startup path can still change schemas without an approval checkpoint.
2. **Confirmed sensitive-input reflection.** Default FastAPI validation responses can contain rejected input, including passwords. Central sanitization should remove input/context payloads while retaining useful safe validation messages.
3. **Sensitive exception/config representations.** SQLAlchemy lacks `hide_parameters=True`; DB errors may include resume text/JSON parameters. Database URL and JWT secret are not excluded from settings repr, unlike the LLM key.
4. **JWT strength and lifecycle.** A development JWT default is permitted. The current configured secret is nondefault but shorter than 32 characters. Logout clears browser storage; it does not revoke an already issued JWT. No authentication throttling is implemented. Secret rotation needs coordination because it invalidates active tokens.
5. **Duplicate reachable backend.** `frontend/app/api/[...path]/route.ts` exposes different auth/session/data contracts and keyword-only job analysis. Current UI uses FastAPI. Preserve its data; identify external consumers before disabling/consolidating anything.

### Reliability and correctness

6. **Auth outages appear as logout.** `frontend/hooks/useAuth.ts` clears displayed identity after any /me error, including a network outage; stale responses can restore state after logout/token replacement.
7. **Profile-save race.** `ProfileEditor.tsx` resets local state on new initialData while controls remain editable during save; an in-flight response can erase subsequent edits.
8. **Profile corrections versus generation evidence.** Manual edits update parsed_data; generation/factual checks/scoring use raw_resume_text. Corrected extraction can disagree with the generated context. Define a policy preserving original evidence rather than treating arbitrary edited JSON as verified qualifications.
9. **Outreach stale state.** Changing jobs does not consistently clear prior match/result state; Back/navigation can run during match/generation.
10. **Tracker concurrency.** A single pending ID does not protect multiple simultaneous row updates/deletes.
11. **Clipboard failure.** Clipboard writes are neither awaited nor caught; the UI can claim success after denial.
12. **PDF input mismatch.** Client/backend MIME checks differ; uppercase extension/missing MIME and empty-file handling need alignment. Same-file retries and immediate double-submit prevention need checks.
13. **Gemini failure handling.** Existing output schemas and grounding instructions are good, but invalid key/model/quota/transient errors collapse to a generic response; bounded retry policy is not explicit.
14. **Password rules.** Signup permits one-character passwords. Login inherits signup schema, so stricter signup rules must be separated to preserve existing users.
15. **Build tooling.** Lint is not configured. Requirements are broadly unpinned, so reproducibility needs review without unrequested bulk dependency upgrades.
16. **Performance.** Jobs/drafts endpoints load full owned histories; missing owner indexes and absent pagination will matter as records grow.

No broad mock-record path was found in the active FastAPI-backed frontend. Static marketing copy and option lists are presentation data; mocked Gemini exists in isolated tests. Placeholder keyword extraction belongs to the duplicate Next API.

## Ordered implementation checklist for the next stage

1. Gate schema initialization so normal PostgreSQL startup never runs DDL; keep explicit isolated-test initialization.
2. Sanitize API validation/exception output and settings representations; prevent SQL parameter disclosure. Add synthetic-secret regression checks.
3. Configure noninteractive lint using versions compatible with the existing Next stack; repeat build/types/tests.
4. Strengthen signup validation independently of login; extend auth/ownership tests. Document JWT rotation and session-revocation decisions before changing active credentials or architecture.
5. Classify Gemini errors safely; explicitly bound retries to suitable transient cases. Add mocked key/model/quota/timeout/retry/invalid-output tests. Use existing provider allowance only for an explicitly documented live smoke check; never enable billing.
6. Fix session outage/stale-response handling, upload guards, profile-save races, tracker row concurrency, wizard invalidation, and clipboard feedback using existing components/styles.
7. Define reviewed-profile grounding semantics while preserving raw resume evidence; test persistence and generated context.
8. Preserve current FastAPI routes and table families. Record the duplicate Next API as legacy; avoid silently removing a reachable feature.
9. Prepare detailed index/ownership/status migration proposals and development-branch verification. Execute nothing on production without explicit approval and verified backup.
10. Repeat the isolated full workflow, cross-user/error tests, build, types, and configured lint; then report changed files, exact results, remaining limits, and any approval-required operations.

Stage 1 does not require approval for any production operation because none is proposed for immediate execution. Future production schema changes and credential rotation must remain explicit, reviewable steps.
