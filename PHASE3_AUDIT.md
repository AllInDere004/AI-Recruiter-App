# Phase 3 audit and implementation checkpoint

Date: 2026-11-07 (Asia/Calcutta)
Branch: `feature/phase-3-smart-job-discovery`

## Decision boundary

This document is the required pre-implementation checkpoint. No Phase 3 production
DDL, production DML, provider credential, paid service, recruiter email, or job
application was used. Major implementation is intentionally paused until the first
job provider and durable scheduler approach are approved.

Phase 2 is present in the working tree but its additive migration remains disabled
in production. Phase 3 must therefore test migrations in this order on a new Neon
development branch:

1. `002_career_intelligence.sql`
2. proposed `003_smart_job_discovery.sql`

Production requires a verified backup/restore checkpoint and a separate explicit
approval before either migration is applied.

## Baseline verification

| Gate | Result |
| --- | --- |
| Backend unit/API tests | 159 passed in 7.283 seconds |
| TypeScript | Passed (`tsc --noEmit --incremental false`) |
| ESLint | Passed with no warnings or errors |
| Next production build | Passed; all 12 existing routes generated |
| Phase 1 browser regression | Passed against temporary SQLite and mocked Gemini |
| Phase 2 browser regression | Passed against temporary SQLite and mocked Gemini |
| Patch hygiene before Phase 3 | `git diff --check` passed at the Phase 2 handoff |

The first direct browser-script invocations failed because those scripts are clients
and their documented localhost fixtures were not running. After starting the isolated
fixtures on ports 8002/3001, both suites passed completely. The fixtures were stopped
and the test-only TypeScript include was removed.

Known dependency baseline from the Phase 2 report remains open: 12 advisories (1
critical, 5 high, 6 moderate). No forced audit fix or framework upgrade is authorized
as part of this checkpoint. This is not a production security sign-off.

## Current architecture

### Frontend

- Next.js 14 App Router, React 18, TypeScript, Tailwind, GSAP, and the existing UI
  component system.
- Browser authentication uses the current bearer token flow through `frontend/lib/api.ts`.
- Existing pages: landing, login, signup, onboarding, dashboard, profile, new email,
  draft detail, tracker, and settings.
- `frontend/app/api/[...path]/route.ts` is a duplicate legacy Next API path. The active
  UI uses the FastAPI URL configured through `NEXT_PUBLIC_API_URL`.
- The dashboard currently aggregates `jobs` and `drafts`, not application events.
- The tracker is a view over email drafts with statuses `Draft`, `Sent`, `Replied`,
  `Interview`, and `Rejected`. It has a select-based accessible status alternative,
  but no drag-and-drop, application entity, immutable activity history, reminder,
  deadline, interview model, or optimistic concurrency token.

### Backend

- FastAPI, Pydantic, SQLAlchemy ORM, psycopg2, JWT authentication, and Google Gemini.
- All current private FastAPI routes derive ownership from the authenticated `User`.
- Existing active modules cover authentication, resume/profile persistence, job-text
  analysis, deterministic/semantic matching, email drafts, Phase 2 career intelligence,
  immutable resume/document versions, and exports.
- `backend/app/scheduler.py` is empty. There is no durable worker or scheduler in the
  current deployment architecture.
- PostgreSQL startup performs no implicit DDL. SQLite test fixtures retain isolated
  automatic initialization.
- Existing AI request limits are process-local. A separate bounded limit will be
  required for provider search and URL import.

### Active data model

- `users`: active FastAPI identities.
- `profiles`: one current resume/profile per active user.
- `jobs`: user-owned, manually supplied/analyzed job descriptions. This is not a
  provider listing catalogue.
- `drafts`: user-owned generated emails plus the current draft-centric tracker status.
- Phase 2 development models: `resume_versions`, `career_reports`, and
  `generation_versions`; proposed and tested, but not present in production.

### Legacy/duplicate model

`recruiter_users`, `recruiter_profiles`, `recruiter_jobs`, `recruiter_drafts`,
`recruiter_sessions`, and `recruiter_migrations` belong to the duplicate legacy Next
server path. They must remain untouched. Phase 3 should use the active FastAPI entities.

## Read-only Neon production audit

The configured production connection was inspected without reading row values:

- Database: `neondb`
- `SELECT 1`: succeeded
- Tables: `users`, `profiles`, `jobs`, `drafts`, `recruiter_users`,
  `recruiter_profiles`, `recruiter_jobs`, `recruiter_drafts`, `recruiter_sessions`,
  `recruiter_migrations`
- Foreign keys: 9
- Indexes: 13
- Phase 2 tables present in production: no
- Production schema/data changed by this audit: no

The application keeps its existing SQLAlchemy/psycopg2 connection approach. Normal
application traffic may use a pooled Neon URL; reviewed migrations must use a direct,
non-pooler URL on an isolated branch.

## Existing UI-to-API map

| UI | Active API/data path |
| --- | --- |
| Login/signup | `/api/auth/register`, `/api/auth/login`, `/api/auth/me` |
| Onboarding/profile | `/api/resume/upload`, `/api/profile/me` |
| New email | `/api/jobs/analyze`, `/api/jobs/`, `/api/match/compare`, `/api/email/generate` |
| Tracker/draft detail | `/api/drafts/`, `/api/drafts/{id}` |
| Phase 2 panels | `/api/intelligence/status`, resumes, reports, documents, exports |
| Dashboard | Client aggregation of jobs, drafts, Phase 2 reports/documents |

## Broken or incomplete Phase 3 flows

- No external job provider, source attribution, freshness, pagination, or provider
  outage behavior exists.
- No HTTPS job URL import or SSRF boundary exists.
- `jobs` has no source URL/provider identity and no provider-level deduplication.
- Saved jobs are inferred from analyzed jobs; there are no bookmarks, tags, notes,
  archive state, or preference records.
- An email draft currently doubles as an application card. Deleting a draft deletes
  the only tracker record and there is no append-only history.
- Dashboard counts are real for jobs/drafts but do not have application semantics.
- No timezone preference, reminder, notification, scheduler, status transition policy,
  manual submission confirmation, or concurrent update protection exists.
- Browser test Gemini responses are intentionally mocked; they are not fake live jobs.
  No fake job fallback should be introduced.

## Provider comparison

Research used current official provider documentation on 2026-11-07.

| Provider | Coverage/use | Access and limits | Terms/attribution | Assessment |
| --- | --- | --- | --- | --- |
| Jooble India | Broad India keyword/location search through `in.jooble.org` | India-specific API key; free API has a 500-request lifetime quota | Preserve source/link and comply with Jooble terms | Recommended first broad-search adapter, pending approval to add a server-side key |
| Adzuna | Broad India catalogue and search | `app_id` + `app_key`; free evaluation key without payment details | Required Adzuna attribution; commercial use has a 14-day trial then needs written licence | Good second adapter, but unsuitable for ongoing commercial use without licensing approval |
| Remotive | Remote jobs only | Public API; advised at most four refreshes/day and requests over 2/min may be blocked | Must link to and name Remotive; 24-hour delay; listings may not be gated to collect signups/emails | Not selected for this authenticated app without written confirmation that the use complies |
| Greenhouse Job Board | Public jobs for one known company board | Public GET endpoints; no key for reads | Designed for an individual organization's published board | Useful structured URL-import adapter, not a broad discovery search provider |
| Lever Postings | Public jobs for one known company site | Public HTTPS postings endpoint | Designed for an individual company's published postings | Useful structured URL-import adapter, not a broad discovery search provider |

### Provider recommendation

Use Jooble India as the initial broad discovery provider, behind a modular adapter and
feature/readiness status. Required server-side configuration would be:

- `JOB_PROVIDER=jooble`
- `JOOBLE_API_KEY` (secret; never exposed to the browser or logs)
- `JOOBLE_API_BASE_URL=https://in.jooble.org/api`
- conservative application search and cache limits below the provider's lifetime quota

No key has been requested, stored, or tested. If provider approval is withheld, Phase 3
can still implement the adapter contract, secure URL import, manual paste fallback, and
all internal application-management features; live broad search must clearly report
"provider not configured" and must not return fixtures as live data.

## Proposed module map

### Backend additions

- `backend/app/api/discovery.py`: authenticated search, listing details, URL-import
  preview, review/save, recommendation endpoints.
- `backend/app/api/applications.py`: saved jobs, applications, transitions, linked
  document versions, events, reminders, notifications, analytics, and activity.
- `backend/app/models/discovery.py`: additive Phase 3 ORM entities.
- `backend/app/schemas/discovery.py`: bounded request/response contracts.
- `backend/app/providers/base.py`: provider protocol and normalized listing model.
- `backend/app/providers/jooble.py`: Jooble adapter, timeout/error/quota mapping, and
  normalization. No silent fallback provider.
- `backend/app/services/job_import.py`: HTTPS/DNS/redirect/content-size/content-type
  enforcement, structured `JobPosting` extraction, safe text extraction, and review.
- `backend/app/services/recommendations.py`: Phase 2 deterministic scoring over genuine
  current listings and user preferences.
- `backend/app/services/application_service.py`: transition policy, ownership,
  optimistic concurrency, and append-only event writes.
- `backend/app/services/reminders.py`: UTC due-time logic, idempotent claiming/delivery,
  snooze/dismiss/complete behavior.
- `backend/app/services/analytics.py`: explicit user-scoped SQL aggregations.
- `backend/migrations/003_smart_job_discovery.sql`: reviewed additive proposal only.
- `backend/scripts/verify_phase3_development.py`: production refusal, schema validation,
  synthetic transactional tests, and unchanged-original-schema assertions.

### Frontend additions/edits

- Add `/jobs` and `/jobs/[id]` pages using the existing shell/design system.
- Add discovery filters, provider/freshness attribution, explicit external apply links,
  URL import review, saved-job controls, and honest provider-empty/error states.
- Extend `/tracker` and `TrackerBoard` rather than replace them. Existing drafts remain
  accessible; new application cards use the Phase 3 application API.
- Enhance `/dashboard` with database analytics and upcoming reminders.
- Add activity/reminder panels and accessible status controls alongside drag-and-drop.
- Extend `frontend/lib/api.ts` and `frontend/types/index.ts`; preserve all existing calls.

## Proposed additive database model

No existing table is deleted, renamed, truncated, merged, or repurposed.

1. `external_job_listings`
   - provider + provider job ID unique key, normalized public fields, official apply URL,
     source URL, content fingerprint, published/fetched/expiry timestamps, raw normalized
     JSON only (no provider secret).
2. `saved_jobs`
   - user-owned bookmark linking an external listing and optional active `jobs` analysis
     row; notes, tags JSON, archived timestamp; unique user/listing constraint.
3. `job_preferences`
   - one user-owned row for roles, locations, remote policy, experience levels, job
     types, and timezone.
4. `applications`
   - user-owned application linked to a saved job/job; eight canonical states,
     submission confirmation timestamp, application/interview/deadline fields,
     recruiter contact metadata, approved resume/email/cover-letter version IDs, and
     integer `version` for optimistic concurrency.
5. `application_events`
   - append-only owner/application event history with bounded non-sensitive context JSON.
6. `reminders`
   - owner/application, UTC due time, timezone-at-creation, state, snooze/delivery
     metadata, idempotency key, lease/attempt fields, and version.
7. `notifications`
   - owner/reminder, in-app payload, read/dismissed timestamps, unique delivery key.
8. `recommendation_cache`
   - owner, listing, profile/job/preference versions, deterministic result JSON,
     listing freshness, algorithm version, and unique input hash.

Indexes will cover provider identity/freshness, user + saved/archive state, user +
application status/date, event pagination, reminder due-state claims, notification
unread queries, and recommendation input uniqueness. Composite owner foreign keys will
prevent cross-user linkage where practical.

## Status and analytics semantics

Canonical application states: `Saved`, `Preparing`, `Applied`, `Assessment`,
`Interview`, `Offer`, `Rejected`, `Withdrawn`.

- External submission is never inferred. Moving to `Applied` requires explicit user
  confirmation and stores `submitted_at`.
- Every accepted state change and meaningful linkage writes one application event in
  the same transaction.
- Analytics count applications, not events. A current-state count uses the latest
  application row; conversion metrics use the first qualifying append-only event per
  application to avoid duplicate transitions.
- Response rate denominator: applications confirmed submitted in the selected range.
  Numerator: those with a first `Assessment`, `Interview`, `Offer`, or `Rejected` event.
- Interview and offer conversion denominators are confirmed submitted applications;
  each application contributes at most once to each numerator.
- Average match score includes only persisted Phase 2 match reports linked to included
  applications and is labeled unavailable when none exist.

## Security plan

- Authentication and authenticated ownership on every private endpoint.
- Provider credentials remain server-only and are redacted from exception paths.
- Imported URLs require HTTPS, normalized ports, bounded redirect count, DNS resolution
  before every connection, rejection of private/loopback/link-local/multicast/reserved
  IPv4/IPv6 destinations, response streaming limits, MIME allowlists, and timeouts.
- DNS answers must be pinned/verified at connection time to address rebinding; a normal
  high-level HTTP redirect-following client is insufficient by itself.
- Prefer official Greenhouse/Lever structured endpoints for recognized URLs. Respect
  robots and provider restrictions; otherwise require manual paste.
- Imported descriptions are stored/displayed as plain text, never unsanitized provider
  HTML. Embedded instructions remain untrusted job content passed through existing
  strict job schemas/evidence rules.
- Search/import/AI endpoints receive separate authenticated quotas. Provider failures
  return explicit retryable/unavailable errors and never test fixtures.
- Reminder delivery uses a unique idempotency key plus an atomic lease/claim transaction.

## Scheduler checkpoint

An in-process FastAPI scheduler is not durable across restarts or multiple replicas and
will not satisfy the brief. The proposed design exposes an authenticated internal
worker that atomically claims due reminders and creates in-app notifications. It still
needs a durable external trigger.

Two acceptable deployment choices require approval/configuration:

1. Existing hosting-provider cron calls the internal worker (preferred if the current
   host already supplies durable cron).
2. A Neon Function Trigger or queue invokes the worker. This adds deployment
   infrastructure and may affect billing, so it will not be enabled automatically.

Email notifications remain out of scope until separate consent, provider, credential,
and billing approval. Recruiter email is never automatic.

## Implementation stages after approval

1. Provider contract, Jooble adapter with mocked tests, readiness endpoint, no-key state.
2. Secure URL-import preview and manual-paste fallback.
3. Phase 2 recommendation integration and safe cache.
4. Additive models/migration plus local SQLite and schema-only Neon branch validation.
5. Saved jobs and applications with event history/concurrency.
6. Reminders/notifications plus approved durable trigger integration.
7. Analytics/activity endpoints.
8. Frontend discovery, enhanced tracker, dashboard, reminders, and activity.
9. Security, unit, integration, browser, Phase 1/2 regression, and final report.

## Approval required before major implementation

1. Approve Jooble India as the initial provider and creation of server-side environment
   placeholders for its API key. No payment will be enabled.
2. Identify/approve the durable scheduler path: existing host cron, or a separately
   reviewed Neon Function Trigger/queue.

Production migration approval is intentionally not requested yet. It becomes eligible
only after `003_smart_job_discovery.sql` is reviewed and both migrations pass on a new
Neon development branch with a verified production backup/restore checkpoint.
