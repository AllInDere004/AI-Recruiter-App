# Local development activation report

Verified on 2026-11-11 (Asia/Calcutta). No deployment was performed.

## Database isolation

- Active local branch: `local-development-20261110`
- Branch ID: `br-green-wave-azi7jupr`
- Database: `neondb`
- Parent: production branch `br-summer-bread-az2p9coe`
- Default/primary/protected: no/no/no
- Expiry: `2026-12-10T11:30:00Z`
- Local runtime endpoint: verified as the development branch endpoint
- Runtime connection: pooled TLS (`sslmode=require`)
- Migration connection used during setup: direct TLS
- Schema: 31 tables; migrations 002, 003, and 004 present

The existing rehearsal branch was verified as non-production with all 31 tables.
Because Neon does not allow children of an expiring branch, the dedicated local
branch was created from production and migrations 002-004 were applied only to that
new non-default branch. Original rows and schema were preserved.

The former production connection is stored only in the ignored local file
`backend/.env.production.local`. The effective `backend/.env` points to the dedicated
development branch. Neither file is tracked by Git, and no credential is included in
this report.

Final read-only comparison:

- Production: 10 tables; `SELECT 1` passed; original per-table counts unchanged
- Development: 31 tables; `SELECT 1` passed; feature test records present
- Production and development endpoints: different
- Production migrations 002-004: absent

## Effective local configuration

- `ENVIRONMENT=development`
- `JOB_PROVIDER=himalayas`
- `ENABLE_CAREER_INTELLIGENCE=true`
- `ENABLE_JOB_DISCOVERY=true`
- `ENABLE_ADVANCED_FEATURES=true`
- `ENABLE_GMAIL=false`
- `HIMALAYAS_API_KEY`: configured
- `LLM_API_KEY`: configured
- `LLM_MODEL`: configured

No credential value was printed, logged, or copied into frontend configuration.

## Live feature verification

### Job Discovery — PASS

- Authenticated `/api/discovery/status`: enabled and ready
- Provider: Himalayas; configured
- Real bounded search: passed
- Filters, sorting, and page 2 pagination: passed
- Save/bookmark: passed
- Preferences and recommendations: passed
- Resume/job match report: passed
- Application creation, confirmed submission, and Interview transition: passed
- Provider fixtures were not used

### Interview Practice — PASS

- Authenticated `/api/interviews/status`: enabled and ready
- Approved resume selection: passed
- Live Gemini technical question generation: passed
- Answer submission: passed
- Live Gemini structured evaluation: passed
- Practice score and feedback persistence: passed
- Interview history: passed
- Gmail remained disabled

### Career Analytics — PASS

- Application funnel using Neon development data: passed
- Submitted/interview metrics: passed
- Stage filter: passed
- Weekly/application summary: passed
- Interview session and evaluation metrics: passed

### Authentication and UI — PASS

- Unauthenticated status routes rejected: passed
- Separate second user could not access the first user's application, interview, or report: passed
- Second user's private lists remained empty: passed
- Existing profile and jobs routes: passed
- Authenticated Job Discovery, Interview Practice, and Career Analytics pages rendered
- Midnight + Solar Ember components and styles were preserved
- No browser runtime errors occurred

## Safe fixes made during activation

1. New resume uploads with Career Intelligence enabled failed before snapshot creation
   because `SessionLocal` disables autoflush. `resume.py` now explicitly flushes the
   new profile before querying it for an immutable resume snapshot.
2. Gemini accepted question generation but rejected the deeply constrained interview
   feedback JSON Schema as having too many serving states. The provider now receives
   a compact equivalent schema; the existing strict Pydantic validation, ownership
   checks, rubric categories, evidence-substring checks, and score bounds still run
   after generation.
3. Legacy Phase 1 profile tests now explicitly disable optional Phase 2-4 flags so
   their result does not depend on a developer's local environment.

## Test results

- Live authenticated API workflow: passed
- Live authenticated frontend workflow: passed
- Full backend suite: **193 passed, 0 failed**
- Focused Career Intelligence suite: 13 passed
- Focused Gemini reliability and interview suites: 11 passed
- TypeScript (`tsc --noEmit`): passed
- ESLint: passed, no warnings
- Optimized Next.js build: passed; 17 routes generated
- Backend `http://127.0.0.1:8002/ready`: ready
- Frontend `http://127.0.0.1:3000`: reachable

## Remaining local-development notes

- The development branch expires on 2026-12-10. Create or extend an isolated branch
  and update the ignored local env before that date if testing continues.
- Synthetic smoke-test records remain in the development branch because destructive
  cleanup was prohibited. They do not exist in production.
- The local JWT secret was rotated to 48 cryptographically random bytes after the JWT
  library warned that the previous 28-byte value was below the HS256 recommendation.
  Existing browser sessions created before the rotation must sign in again.
- Gmail intentionally remains disabled. No email was sent and no paid service was enabled.
