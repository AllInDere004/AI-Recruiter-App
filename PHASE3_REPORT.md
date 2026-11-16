# Phase 3 implementation report

Date: 2026-11-07 (Asia/Calcutta)
Branch: `feature/phase-3-smart-job-discovery`

## Outcome and activation boundary

Phase 3 Smart Job Discovery and Application Management is implemented and verified in
isolated environments. Production remains unchanged: its original ten tables are
preserved, the Phase 2/3 tables are absent, and `ENABLE_JOB_DISCOVERY` defaults to
false. No external application was submitted and no recruiter email was sent.

Production activation is not approved by the Phase 3 implementation approval. It still
requires a verified production backup/restore checkpoint, review of migrations 002 and
003, explicit production migration approval, and deployment configuration for the
provider key and reminder trigger.

## Implemented capabilities

### Genuine provider discovery

- Modular provider protocol and a Jooble India adapter.
- Server-only credential, bounded timeout/response size, safe provider errors, explicit
  quota/auth/outage states, pagination, filters, sorting, normalization, provider ID
  deduplication, source attribution, official application URL, and freshness.
- Results are persisted only when the feature schema is active. Provider failure never
  substitutes fixtures or invented jobs.
- Jooble calls were mocked only in unit/browser fixtures and are labeled isolated test
  data. Live Jooble search was not executed because no real key was configured.

### URL and manual import

- HTTPS-only URL validation with no embedded credentials or nonstandard ports.
- DNS resolution rejects any private, loopback, link-local, multicast, reserved, or
  unspecified IPv4/IPv6 answer.
- DNS is resolved and checked at every redirect. Production retrieval pins the public
  IP while preserving TLS SNI/certificate validation for the original hostname.
- Redirect, timeout, content length, streaming size, and MIME limits.
- Conservative robots handling; blocked/unavailable sites direct users to manual paste.
- Structured `JobPosting` JSON-LD is preferred. HTML is converted to plain text and is
  never rendered as provider HTML.
- Existing strict Gemini job analysis normalizes safe retrieved/pasted text. The user
  must review/correct the preview before saving.

### Recommendations

- Reuses the Phase 2 deterministic evidence engine.
- Career compatibility remains distinct from preference fit. Ranking is 85% Phase 2
  compatibility and 15% explicit preferences.
- Shows required mismatches, preferred gaps, weighted categories, preference reasons,
  source freshness, and a hiring-success disclaimer.
- Only active persisted genuine/imported listings are ranked.
- Cache keys bind the approved resume fingerprint, listing fingerprint, preferences
  version, and algorithm version; cache entries expire after one hour.

### Saved jobs and preferences

- Owner-scoped bookmarks, tags, notes, archive, search, tag filtering, persistence,
  provider identity, source URLs, and timestamps.
- Duplicate user/listing records are rejected.
- Preferred roles, locations, work mode, experience levels, job types, and IANA timezone.

### Applications and history

- Separate application entity instead of treating email drafts as applications.
- Eight states: Saved, Preparing, Applied, Assessment, Interview, Offer, Rejected, and
  Withdrawn.
- Drag-and-drop plus a keyboard/select alternative. Existing draft tracker remains
  available below the application board.
- Applied requires explicit confirmation that submission occurred on the official site.
- Optimistic integer versions and row locks reject stale concurrent changes.
- Approved Phase 2 resume/email/cover-letter links are owner-validated.
- Status and meaningful update/reminder events are append-only and exclude private text.

### Reminders and notifications

- UTC storage with validated IANA timezone metadata (`tzdata` added for Windows/runtime
  portability).
- Upcoming, overdue, completed, snoozed, and dismissed behavior.
- Atomic due-row claiming, unique delivery keys, retry counters, and idempotent in-app
  notification creation.
- User-scoped process-on-load endpoint plus a server-token protected durable-worker
  endpoint. No external scheduler or paid infrastructure was enabled.
- Email notifications and automatic recruiter email remain disabled.

### Analytics and activity

- User-scoped real database counts for total/submitted applications, current states,
  interviews, offers, rejections, response/interview/offer conversion, daily trend, and
  available Phase 2 match scores.
- Denominator: explicitly confirmed submitted applications in the requested range.
- Conversion numerators use distinct applications with a qualifying event, preventing
  repeated transitions from double counting.
- Empty denominators return null rates rather than invented metrics.
- Paginated, filterable activity endpoint with related application IDs and bounded
  non-sensitive context.

## Data model and migration

`003_smart_job_discovery.sql` creates only:

- `external_job_listings`
- `saved_jobs`
- `job_preferences`
- `applications`
- `application_events`
- `reminders`
- `notifications`
- `recommendation_cache`

It does not alter, rename, truncate, delete, or merge an existing table. Composite owner
foreign keys protect saved-job/application/event/reminder/document relationships.
Indexes cover provider freshness, saved/archive queries, application status/dates,
activity pagination, due reminder claims, unread notifications, and cache expiry.

Development verification branch:

- Name: `phase3-smart-job-discovery-20261107`
- ID: `br-flat-fog-azl6aupx`
- Schema-only; no production rows copied.
- Non-default, non-primary, direct TLS connection, production endpoint explicitly
  excluded, expires 2026-11-09 at 18:00 UTC.
- Migrations 002 then 003 applied and validated. A subsequent idempotent verifier pass
  found both schemas present.
- Original tables/metadata remained identical; synthetic ownership, status, history,
  reminder, notification and cache checks passed and rolled back.

See `PHASE3_MIGRATION_TEST.md` for the metadata-only result.

## Security results

- All user data endpoints require authentication and derive ownership from the JWT user.
- Cross-user listing saves, applications, reminders, notifications, document links and
  activity access are rejected or return no records.
- SQLAlchemy parameterization is preserved; no raw client SQL exists.
- Imported HTML is never rendered; URL and provider strings are displayed as React text.
- Search/import/AI calls have separate process-local quotas. A distributed limiter is
  still required for multi-worker production.
- Provider/API secrets are marked non-repr and never returned by application endpoints.
- Worker authentication uses constant-time token comparison and is disabled when unset.

During development-branch creation, the Neon CLI unexpectedly printed a newly created
development connection credential in its own JSON response. That development-branch
password was immediately rotated and invalidated before migration testing continued.
All later CLI responses were captured in memory, and no credential is stored in the
reports or source. Production DDL/DML was not executed.

## Verification results

| Check | Result |
| --- | --- |
| Expanded backend unit/API/security/migration suite | 174 passed in 12.607 seconds |
| TypeScript | Passed after the production build completed |
| ESLint | Passed with zero warnings/errors |
| Next production build | Passed; `/jobs` and `/jobs/[id]` included |
| Phase 1 browser regression | Passed on warm isolated fixtures |
| Phase 2 career browser regression | Passed |
| Phase 3 browser regression | Passed |
| Neon development migration verification | Passed |
| Production `SELECT 1` / inventory | Passed at audit; ten original tables |

The first cold Phase 1 browser attempt submitted before React hydration and timed out
without calling the registration API. The unchanged suite passed after the development
page compiled. This is a test-harness cold-start limitation, not an application assertion
failure.

## Deployment configuration

Server-only environment variable names are documented in `backend/README.md`:

- `ENABLE_JOB_DISCOVERY`
- `JOB_PROVIDER`
- `JOOBLE_API_KEY`
- `JOOBLE_API_BASE_URL`
- `JOB_SEARCH_REQUESTS_PER_MINUTE`
- `JOB_IMPORT_REQUESTS_PER_MINUTE`
- `JOB_PROVIDER_TIMEOUT_SECONDS`
- `JOB_IMPORT_MAX_BYTES`
- `REMINDER_WORKER_TOKEN`

No value is committed. Do not prefix secrets with `NEXT_PUBLIC_`.

## Remaining limitations

1. A real Jooble India credential is not configured/tested. Its documented free quota is
   500 lifetime API requests; production caching and licensing/terms must be monitored.
2. Arbitrary live URL retrieval was not exercised against third-party sites in E2E.
   SSRF/redirect/content behavior is adversarially unit-tested; real sites may block
   retrieval and require manual paste.
3. A durable cron/queue/Neon Function trigger is not deployed because the hosting target
   and any billing impact remain unknown. The authenticated worker contract is ready.
4. Search/import quotas are process-local. Multi-replica production needs a shared store.
5. Jooble snippets may omit full requirements. Recommendations disclose missing source
   detail and cannot predict employer decisions.
6. Existing JWT localStorage, secret strength, login throttling, duplicate legacy Next
   API, and the Phase 2 dependency advisories remain separate hardening work.
7. The dependency baseline remains 12 advisories (1 critical, 5 high, 6 moderate). No
   forced framework upgrade was performed; this is not a production security sign-off.
8. No production backup was taken, so production migration remains blocked.

## Main changed files

Backend: discovery/application routers, discovery schemas/models, Jooble provider,
SSRF-safe import service, recommendations, application transitions, reminders,
request limits, migrations 003, development verifier, Phase 3 tests, fixture updates,
configuration, runtime requirements, main registration, and README.

Frontend: `/jobs`, `/jobs/[id]`, discovery and application tracker components, sidebar,
dashboard, existing tracker integration, API client, types, and Phase 3 browser test.

No existing route or feature was removed.
