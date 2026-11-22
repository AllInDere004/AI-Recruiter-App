# Phase 4 — Advanced Features & Production Readiness: Stage 1 Audit

Audit date: 2026-11-08 (Asia/Calcutta)
Working branch: `feature/phase-4-production-readiness`
Scope: read-only repository, configuration, dependency, browser-fixture, and production database audit. No Phase 4 feature implementation, production migration, deployment, email send, paid-service activation, or administrator provisioning was performed.

## Executive assessment

The Phase 1–3 application is functionally healthy in its isolated test environment, but it is not ready for a Phase 4 production release. The most important blockers are:

1. All Phase 1–3 work remains uncommitted. `main` and the Phase 1–3 branches still point to the same original baseline commit, so there is no reviewable or recoverable release boundary.
2. Two backend architectures coexist: the primary FastAPI/SQLAlchemy API and a legacy Next.js catch-all API with a different authentication model and `recruiter_*` schema. A production deployment could select different behavior depending on `NEXT_PUBLIC_API_URL`.
3. The production database contains only the ten original tables. The Phase 2 and Phase 3 migrations are not active in production, and their feature flags remain disabled.
4. Current dependency scanning reports 12 frontend advisories: 1 critical, 5 high, and 6 moderate. The direct packages implicated include Next.js, Zod, and `eslint-config-next`.
5. There is no CI workflow, the backend Dockerfile is empty, the scheduler module is empty, no production host is declared, and no staging deployment exists.
6. Authentication stores a bearer JWT in browser `localStorage`; the FastAPI token has a fixed 30-minute lifetime and no refresh/revocation design. The legacy Next API instead creates seven-day database sessions.
7. Production CORS is not configurable and currently permits localhost only. Security headers, trusted-host enforcement, structured logging, monitoring, and durable distributed rate limiting are absent.

The safest implementation path is incremental: first establish a clean Phase 1–3 commit/review boundary, then implement Phase 4 behind feature flags and validate additive migration `004` on an expiring schema-only Neon branch. Production must remain unchanged until backup/restore evidence and explicit approval are supplied.

## Baseline evidence

### Git and working tree

- A Phase 4 feature branch was created without modifying or discarding the existing working tree: `feature/phase-4-production-readiness`.
- Current commit: `8c42636`, the original pre-Phase-1 baseline.
- `main`, `feature/phase-1-core-reliability`, `feature/phase-2-career-intelligence`, and `feature/phase-3-smart-job-discovery` all point to that same commit.
- Phase 1–3 source, migrations, tests, and reports are a mixture of modified and untracked files.
- No commit was created because committing the combined Phase 1–3 working tree requires a deliberate review decision.

### Executed tests and checks

| Check | Result |
| --- | --- |
| Backend pytest | 174 passed, 36 subtests passed in 12.48 seconds |
| Frontend ESLint | Passed with zero warnings/errors |
| TypeScript `tsc --noEmit --incremental false` | Passed |
| Next.js production build | Passed; 13 pages generated |
| Phase 1 browser suite | First cold-dev-server run failed before React hydration; warm rerun passed completely |
| Phase 2 isolated browser suite | Passed completely |
| Phase 3 isolated browser suite | Passed completely |
| Credential-shaped source scan | Passed; environment files and generated/vendor directories excluded |
| Production `SELECT 1` | Returned `1` in a read-only transaction |

The Phase 1 cold failure submitted the signup form as a native GET before hydration and never made the registration API call. The unchanged warm suite passed. This is a browser-harness readiness defect that should be fixed before CI by waiting for an explicit client-ready marker.

Browser regressions used temporary SQLite, a mocked Gemini SDK boundary, and a mocked Jooble adapter on localhost. The fixtures blocked non-local API destinations. Test servers were stopped, temporary build output was removed, and ports 3001/8002 were clear afterward.

### Measured frontend baseline

- Next.js 14.2.35 production build.
- Shared first-load JavaScript: 87.3 kB.
- Largest current route: `/tracker`, 19.3 kB route size and 156 kB first load.
- `/new-email`: 10.3 kB route size and 153 kB first load.
- No `next/dynamic` or React lazy-loading boundary is currently used.
- Cold development compilation of `/signup` took about 3.0 seconds in the browser fixture; the warm request took about 70 ms. These are local development measurements and are not production latency claims.

### Dependency baseline

Current `npm audit --json` result:

- Critical: 1 (`next`, direct)
- High: 5 (`eslint-config-next` direct, `zod` direct, and transitive Next/PostCSS/glob packages)
- Moderate: 6 (TypeScript ESLint/minimatch transitive packages)
- Total: 12

No Python vulnerability scanner is configured. Most Python runtime dependencies are not version-pinned, reducing build reproducibility. `pip check` reports no broken installed requirements, but that is not a vulnerability assessment.

## Architecture map

```text
Browser / Next.js 14 App Router
  ├─ Established workspace UI, Tailwind, GSAP, React Query, Recharts
  ├─ Bearer token stored in localStorage
  ├─ NEXT_PUBLIC_API_URL -> FastAPI (intended Phase 1–3 path)
  └─ /api/[...path] -> legacy Next.js/pg API (second backend path)

FastAPI
  ├─ OAuth2 bearer JWT, bcrypt password hashes
  ├─ SQLAlchemy ORM + psycopg2
  ├─ Google Gemini through google-genai
  ├─ Jooble provider adapter
  ├─ Resume/profile/job/email/career intelligence services
  ├─ Job discovery/import/recommendation services
  └─ Applications/reminders/notifications/analytics services

Neon PostgreSQL (neondb)
  ├─ Pooled DATABASE_URL for application traffic, sslmode=require
  ├─ Direct DATABASE_URL_UNPOOLED available for migrations
  ├─ Production branch: default, not protected
  ├─ Production: ten original tables only
  └─ Expiring Phase 3 schema-only branch exists until 2026-11-09 18:00 UTC

External providers
  ├─ Gemini: server-side key; LLM_API_KEY and GEMINI_API_KEY aliases accepted
  ├─ Jooble: adapter exists; disabled without key/feature flag
  └─ Gmail: no OAuth or send integration exists
```

## Existing application inventory

### Frontend

Framework: Next.js App Router, React 18, TypeScript, Tailwind CSS.

Routes:

- `/`, `/login`, `/signup`, `/onboarding`
- `/dashboard`, `/profile`, `/settings`
- `/new-email`, `/drafts/[id]`
- `/jobs`, `/jobs/[id]`
- `/tracker`
- `/api/[...path]` legacy server route

No interview-practice, interview-history, admin, notification-center, Gmail-connect, or advanced-analytics route exists.

### FastAPI endpoints

Existing domains include:

- Authentication: register, login, current user
- Resume/profile: PDF upload, parsing, profile review/update
- Jobs/matching: analysis, listing, deterministic comparison
- Email/drafts: generated recruiter drafts and draft history
- Career intelligence: reviewed resume versions, reports, generated documents, exports
- Discovery: provider status/search, secure URL/manual import, saved jobs, preferences, recommendations
- Applications: eight-state tracker, event history, reminders, notifications, analytics, worker endpoint
- Health: database `SELECT 1`

All Phase 4 interview, Gmail, admin, and expanded notification-preference endpoints are absent.

### Data layers

The code defines three groups of tables:

1. Original FastAPI tables: `users`, `profiles`, `jobs`, `drafts`.
2. Original/legacy Next API tables: `recruiter_users`, `recruiter_profiles`, `recruiter_sessions`, `recruiter_jobs`, `recruiter_drafts`, `recruiter_migrations`.
3. Phase 2/3 proposed tables in migrations `002` and `003`: resume versions, career reports, generation versions, external listings, saved jobs, preferences, applications, events, reminders, notifications, and recommendation cache.

Production currently contains groups 1 and 2 only. Phase 2/3 tables are present only in migration code and the isolated Phase 3 development branch.

### Gemini integration

- SDK: `google-genai`.
- Configured model: `gemini-2.5-flash`.
- Server settings accept both `LLM_API_KEY` and `GEMINI_API_KEY`; `LLM_API_KEY` is the canonical setting.
- Structured output uses Pydantic JSON schemas for profile extraction, job analysis, evidence selection, and hallucination checks.
- SDK retries are disabled to avoid duplicate potentially charged generations; requests use a bounded 45-second timeout.
- Error categories cover invalid credentials, unavailable model, quota, timeout, transport, malformed JSON, and empty responses.
- Existing AI request limits are process-local and therefore do not coordinate across multiple production workers.
- Private prompts/answers are not intentionally logged, but structured application logging and centralized redaction are absent.

### Notifications and background work

- Phase 3 reminders support UTC conversion, IANA time zones, snooze/dismiss/complete, row locking, skip-locked claims, retry counters, and unique delivery keys.
- In-app notification creation is idempotent at the database constraint level.
- A token-protected worker endpoint exists.
- No durable scheduler is deployed; `backend/app/scheduler.py` is empty.
- The dashboard currently calls the user-scoped reminder processing endpoint, so delivery can depend on user activity.
- Notification categories/preferences, email consent, and delivery channels are not modeled.

### Deployment and operations

- No GitHub Actions or other CI workflow exists.
- `backend/Dockerfile` is empty.
- No Render/Fly/Vercel deployment manifest or production process declaration exists.
- `neon.ts` declares Postgres only, Neon Auth disabled, and a seven-day TTL for new non-default branches.
- There is no structured log format, error aggregation, uptime monitor, metrics exporter, or alert configuration.
- The health endpoint verifies database connectivity but does not provide separate liveness/readiness semantics or provider status.
- The current production branch is not marked protected in Neon.

## Security and privacy findings

### Critical/high priority

1. **Uncommitted multi-phase release state.** There is no reliable code review, rollback, or release artifact boundary.
2. **Critical/high dependency advisories.** Production release is blocked until upgrades are evaluated and regression-tested; no forced upgrade was applied during this audit.
3. **Dual backend and identity models.** FastAPI JWT users and legacy Next database sessions can diverge in authorization, retention, and deletion behavior.
4. **Browser token storage.** XSS can expose the bearer token because it is stored in `localStorage`. A cookie migration would require CSRF design and explicit compatibility work.
5. **Production schema mismatch.** The application includes Phase 2/3 UI and APIs while production lacks their tables; flags currently prevent activation, but deployment misconfiguration could create partial failures.
6. **No production security headers/host policy.** Trusted hosts, CSP, HSTS, referrer policy, permissions policy, and frame protections are not configured.

### Medium priority

- FastAPI CORS origins are hardcoded to local development.
- Registration/login and AI/job limits are in process memory, so multiple workers bypass a shared ceiling.
- No refresh-token, JWT revocation, password-reset, email-verification, MFA, or session-management workflow exists.
- The health endpoint is public and performs a database query for every request.
- Production database branch protection is disabled.
- Saved-job listing is capped at 200 rather than cursor/page based.
- Some frontend list views request broad collections and render client-side.
- Raw resume text is persisted for evidence workflows; retention/deletion and export policies are not documented across both schemas.
- Account deletion exists only in the legacy Next route and is not exposed consistently through FastAPI.
- There is no admin role model, server-side RBAC, or admin audit trail.
- OAuth token encryption/key rotation infrastructure does not exist.

### Existing positive controls

- Passwords use bcrypt with length/NUL validation and unknown-user timing work.
- JWT decoding requires expiration and subject claims.
- Database/API errors are sanitized; validation responses omit raw private input.
- Most Phase 2/3 records use explicit `user_id` ownership filters and composite ownership constraints.
- Job URL import enforces HTTPS, public-address DNS validation, redirect revalidation, pinned public connections, size/type limits, robots handling, and review tokens.
- Gemini structured output is schema-validated and existing document generation restricts model-selected evidence.
- Reminder processing uses database locks, idempotency keys, and UTC timestamps.
- `.env` files, virtual environments, logs, SQLite fixtures, generated builds, and preview images are ignored.
- The source credential-pattern scan found no credential-shaped values outside excluded local environment/vendor files.

## Phase 4 data proposal

Proposed additive migration: `backend/migrations/004_advanced_features.sql`.

Logical entities:

- `interview_sessions`: owner, job/resume references, type, difficulty, status, question count, optional time limit, model/prompt version, timestamps, optimistic version.
- `interview_questions`: owner/session, immutable order, question type, prompt-safe display text, source/rubric metadata, parent question for follow-ups.
- `interview_answers`: owner/session/question, answer text or encrypted reference, submitted timestamp, retention timestamp. Avoid voice/audio fields.
- `interview_evaluations`: owner/session/question, versioned rubric scores, evidence spans, strengths, improvements, sample answer, model/prompt/rubric metadata, usage metadata.
- `notification_preferences`: one row per user with category/channel consent, timezone, quiet hours, digest limits, optimistic version.
- `gmail_connections`: owner, Google subject/account metadata, encrypted refresh token envelope, scopes, expiry/revocation state. Never return token material.
- `email_send_records`: owner, approved draft reference, recipient/subject hashes or minimal metadata, provider message ID, consent/review timestamps, safe error category.
- `user_roles`: server-managed role assignments with grantor/time metadata. No self-service role field on `users`.
- `admin_audit_events`: actor, action, target type/ID, safe metadata, timestamp, request correlation ID; no resume, answer, email body, or credential content.

All tables should use additive foreign keys, ownership indexes, check constraints, unique idempotency keys where applicable, and explicit deletion/retention behavior. Existing tables will not be renamed, truncated, reset, or destructively altered.

Because production contains private resume/profile data, use an expiring schema-only branch for migration structure and synthetic ownership tests. Neon documents schema-only branches as a Beta privacy feature. Migration execution must use the direct/unpooled URL; normal application traffic keeps the pooled URL.

## Proposed implementation files

### Backend additions

- `backend/app/models/interviews.py`
- `backend/app/models/integrations.py`
- `backend/app/models/admin.py`
- `backend/app/schemas/interviews.py`
- `backend/app/schemas/integrations.py`
- `backend/app/schemas/admin.py`
- `backend/app/api/interviews.py`
- `backend/app/api/notifications.py` (extract/extend Phase 3 APIs without breaking their routes)
- `backend/app/api/integrations.py`
- `backend/app/api/admin.py`
- `backend/app/api/analytics.py` (preserve the existing summary route through compatibility delegation)
- `backend/app/services/interview_engine.py`
- `backend/app/services/interview_feedback.py`
- `backend/app/services/oauth_state.py`
- `backend/app/services/token_encryption.py`
- `backend/app/services/gmail_service.py`
- `backend/app/services/admin_service.py`
- `backend/app/services/analytics.py`
- `backend/app/services/audit_log.py`
- `backend/migrations/004_advanced_features.sql`
- `backend/scripts/verify_phase4_development.py`

### Backend modifications

- `backend/app/config.py`: feature flags, configurable CORS/hosts, OAuth metadata, token-encryption key reference, worker/admin safety settings.
- `backend/app/main.py`: new routers, security middleware, readiness/liveness endpoints, request correlation.
- `backend/app/services/llm_client.py`: interview-safe structured request wrapper, deduplication metadata, usage capture without logging prompts.
- `backend/app/services/reminders.py`: notification preferences/categories while preserving idempotency.
- `backend/app/models/discovery.py` and `backend/app/api/applications.py`: backward-compatible notification and analytics extension only.
- `backend/app/services/auth_service.py`: role lookup and session hardening; no frontend-supplied admin claims.
- `backend/Dockerfile`: reproducible non-root production image after host selection.
- `backend/README.md` and root deployment documentation.

### Frontend additions

- `frontend/app/interviews/page.tsx`
- `frontend/app/interviews/[id]/page.tsx`
- `frontend/app/interviews/[id]/results/page.tsx`
- `frontend/app/analytics/page.tsx`
- `frontend/app/notifications/page.tsx`
- `frontend/app/admin/page.tsx`
- `frontend/components/InterviewPractice.tsx`
- `frontend/components/InterviewResults.tsx`
- `frontend/components/InterviewHistory.tsx`
- `frontend/components/NotificationCenter.tsx`
- `frontend/components/AdvancedAnalytics.tsx`
- `frontend/components/GmailConnection.tsx`
- `frontend/components/AdminDashboard.tsx`

### Frontend modifications

- `frontend/components/Sidebar.tsx`: add only approved Phase 4 navigation using existing styles.
- `frontend/lib/api.ts` and `frontend/types/index.ts`: typed Phase 4 APIs.
- `frontend/app/settings/page.tsx`: notification preferences and optional Gmail controls.
- `frontend/app/dashboard/page.tsx`: real notification/interview summaries only.
- Apply route-level dynamic imports where measured bundle savings justify them.

### Tests and operations

- New backend unit/integration/security suites for interviews, feedback, notifications, Gmail approval/OAuth lifecycle, analytics, admin RBAC, and migration constraints.
- `frontend/scripts/test-phase4-browser.cjs` using SQLite, mocked Gemini, mocked Gmail, and non-production destination guards.
- `.github/workflows/ci.yml` for install, secret scanning, lint, type checks, tests, and build.
- A separate manually approved deployment workflow only after hosting and secrets are configured.
- Release, rollback, backup/restore, privacy, and known-issues documents.

## Incremental implementation plan

1. **Stabilize source control:** review and commit Phase 1–3 as a known baseline before mixing Phase 4 changes into the same release unit.
2. **Test-harness reliability:** add a hydration/readiness marker and deterministic local server lifecycle.
3. **Schema and domain models:** write additive migration `004`, model ownership/retention, and schema tests; validate on an expiring schema-only branch with synthetic data and rollback.
4. **Interview engine:** strict schemas, versioned prompts/rubrics, question deduplication, timeout/error handling, prompt-injection boundaries, mocked tests.
5. **Interview UI/history:** accessible text-only practice, pause/resume, timer, feedback, empty/error/retry states.
6. **Notifications:** durable worker contract, preferences/categories, idempotent multi-worker delivery. Select/deploy scheduler only after approval.
7. **Analytics:** server-side filtered aggregates, documented denominators, pagination, user scoping, query-plan checks on the development branch.
8. **Admin foundation:** database-backed role assignments, deny-by-default server RBAC, safe health/usage summaries, append-only audit events. Do not provision an administrator.
9. **Optional Gmail:** implement disabled OAuth/state/PKCE/token-encryption and mocked approved-send flow. Do not create cloud credentials, enable APIs, or send mail.
10. **Performance/security hardening:** dependency upgrades, configurable CORS/hosts/headers, shared rate limits if required, query/bundle measurements, account export/deletion consistency.
11. **CI/staging packaging:** reproducible backend image and CI checks; staging configuration only after host/secrets approval.
12. **Release verification:** full regression/E2E/security suite, backup restore evidence, monitoring checks, release and rollback drill. Production deployment remains manual and separately approved.

## Required approvals and checkpoints

No approval is needed to continue local code implementation, mocked tests, documentation, or an expiring isolated development branch.

Explicit approval is required before:

1. Applying any Phase 2, Phase 3, or Phase 4 migration to production.
2. Creating a production backup or performing a restore drill that changes external resources.
3. Enabling or purchasing hosting, queues, schedulers, monitoring, email services, or paid Gemini/provider capacity.
4. Creating Google Cloud credentials, enabling Gmail APIs, configuring production OAuth consent/redirects, or sending a real email.
5. Provisioning any administrator or assigning a privileged role.
6. Changing Neon production branch protection, compute sizing, autoscaling, retention, or other billing-affecting settings.
7. Deploying staging or production, changing DNS/domains, or writing secrets to an external platform.
8. Deleting/resetting any branch or production data.

## Stage 1 decision

Stage 1 is complete. Major Phase 4 implementation should not begin until the Phase 1-3 uncommitted baseline is reviewed and given a durable commit boundary. Production is explicitly not considered ready, and no production state was changed during this audit.
