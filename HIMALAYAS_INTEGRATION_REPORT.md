# Himalayas Job Discovery integration report

**Checked:** 10 November 2026
**Production database modified:** No
**Credential value displayed or logged:** No
**Paid service enabled:** No

## Provider contract

- Default provider: `himalayas`
- Endpoint: `GET https://himalayas.app/jobs/api/search`
- Authentication: optional upstream Bearer key; this app requires its configured
  server key to avoid the shared anonymous allowance.
- Filters used by the app: free-text query, country, employment type, sort, and page.
- Search pagination: 1-based pages, up to 20 results per page.
- Keyed allowance documented by Himalayas: 60 requests/minute and 10,000 requests per
  UTC day; cached responses do not count. A 429 response preserves `Retry-After`.

## Sanitized live check

- `HIMALAYAS_API_KEY` loaded: yes
- Active `JOB_PROVIDER`: `himalayas`
- Bounded real search: passed
- Normalized jobs returned: 5
- Provider attribution: passed
- HTTPS application links: passed
- Database writes during live check: none

## Preserved application behavior

Search filtering, pagination metadata, provider attribution, empty-result messaging,
saved jobs, recommendations, resume/job matching, reviewed URL imports, application
tracking, reminders, and analytics continue through the existing provider-neutral
models and API responses. Jooble remains as an explicit legacy adapter and is no
longer part of Himalayas readiness.

## Database and feature readiness

Migrations `002`, `003`, and `004` passed in order on the expiring schema-only Neon
branch `himalayas-activation-20261110`. Production was endpoint-excluded and unchanged.

- Job Discovery: requires `002`, `003`, and `ENABLE_JOB_DISCOVERY=true` on the target environment.
- Interview Practice: requires `002`-`004`, `ENABLE_CAREER_INTELLIGENCE=true`, and `ENABLE_ADVANCED_FEATURES=true`.
- Career Analytics: application metrics require `002`, `003`, and `ENABLE_JOB_DISCOVERY=true`; interview metrics additionally require `004` and `ENABLE_ADVANCED_FEATURES=true`.

## Regression results

- Backend unit/integration/auth/security/migration tests: 192 passed.
- TypeScript: passed.
- ESLint: passed with no warnings.
- Optimized frontend build: passed; 17 routes generated.
- Phase 1 browser flow: passed.
- Career Intelligence browser flow: passed.
- Himalayas-shaped Job Discovery/application/analytics browser flow: passed.
- Interview Practice browser flow: passed.
