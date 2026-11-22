# Phase 4 performance report

Date: 2026-11-08

## Implemented

- Interview history is paginated and ordered by indexed owner/timestamp keys.
- Migration `004` adds owner/history/status/due-time indexes and uniqueness constraints for idempotent operations.
- Interview evaluation is idempotent; saved evaluations are reused rather than calling Gemini again.
- Gemini requests use bounded structured payloads, answer/job size limits, timeouts/retries from the shared client, and separate interview rate limits.
- Analytics aggregate in PostgreSQL and select identifiers/scores instead of loading private resume or answer bodies.
- Phase 4 tables are checked before optional analytics queries, so environments awaiting migration do not break Phase 1–3 analytics.
- Production builds use Next.js standalone output and non-root Docker runtime images.
- Liveness does not query the database; readiness does, allowing orchestration to distinguish process health from dependency health.

## Measured build baseline

- Next.js production build: successful, 17 static/dynamic routes.
- Shared first-load JavaScript: 87.3 kB.
- Interview page first load: 142 kB.
- Analytics page first load: 141 kB.
- Admin page first load: 140 kB.

## Limits of this verification

No representative production dataset or staging traffic target was authorized, so latency percentiles, concurrent-user capacity, Neon autoscaling behavior, and Gemini quota behavior were not load-tested. Those measurements are required before setting an SLO.
