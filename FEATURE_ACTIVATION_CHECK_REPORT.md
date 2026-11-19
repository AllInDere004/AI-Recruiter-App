# AI Recruiter App Feature Activation Check Report

**Checked:** 10 November 2026
**Method:** Read-only code, loaded-environment, and Neon schema inspection
**Database modifications:** None
**Secrets exposed:** None

## Overall status

| Component | Status |
|---|---|
| Neon database connection | Connected |
| Database SSL | Configured |
| Runtime database connection | Pooled |
| Gemini credential | Configured |
| Himalayas credential | Configured |
| Migration `002` on configured database | Not applied |
| Migration `003` on configured database | Not applied |
| Migration `004` on configured database | Not applied |
| `ENABLE_CAREER_INTELLIGENCE` | Off |
| `ENABLE_JOB_DISCOVERY` | Off |
| `ENABLE_ADVANCED_FEATURES` | Off |

## 1. Job Discovery

**Current status:** Provider integration is ready; production remains blocked by database migrations and its feature flag.

| Requirement | Finding |
|---|---|
| Required live-search provider | Himalayas Remote Jobs API |
| Required credential variable | `HIMALAYAS_API_KEY` |
| Credential configured | Yes |
| New API key necessary | No |
| Provider selector | `JOB_PROVIDER`; built-in default is `himalayas` |
| Provider URL | `HIMALAYAS_API_BASE_URL`; defaults to `https://himalayas.app/jobs/api` |
| Database credential | `DATABASE_URL`; configured |
| Required feature flag | `ENABLE_JOB_DISCOVERY=true` |
| Required migrations | `002_career_intelligence.sql`, then `003_smart_job_discovery.sql` |
| Gemini dependency | Existing Gemini credential is sufficient for URL/manual job-description analysis |

### Activation steps

1. Keep the existing Himalayas key in the server-side environment.
2. Select the intended Neon branch. Use a direct, non-pooled, TLS connection for migrations; keep the pooled URL for normal application traffic.
3. Apply `backend/migrations/002_career_intelligence.sql`.
4. Apply `backend/migrations/003_smart_job_discovery.sql`.
5. Set `ENABLE_JOB_DISCOVERY=true`.
6. For the complete resume-based recommendation flow, also set `ENABLE_CAREER_INTELLIGENCE=true` so users can create approved resume versions.
7. Restart the backend because settings are loaded at process startup.
8. Using an authenticated account, verify `GET /api/discovery/status` reports `enabled`, `ready`, and `provider_configured` as true.
9. Run a small live search and a reviewed manual import.

The legacy Jooble adapter remains available for explicitly configured older deployments, but it is not required for readiness.

## 2. Gemini Interview Practice

**Current status:** Blocked by database migrations and feature flags. Its Gemini credential is already configured.

| Requirement | Finding |
|---|---|
| Required AI provider | Google Gemini through `google-genai` |
| Preferred credential variable | `LLM_API_KEY` |
| Accepted credential alias | `GEMINI_API_KEY` |
| Effective Gemini credential configured | Yes |
| Currently configured name | `LLM_API_KEY` |
| New API key necessary | No |
| Model variable | `LLM_MODEL`; configured |
| Required flags | `ENABLE_CAREER_INTELLIGENCE=true` and `ENABLE_ADVANCED_FEATURES=true` |
| Required migrations | `002`, `003`, then `004` |

### Activation steps

1. Keep the existing `LLM_API_KEY`; do not create another Gemini key.
2. Confirm `LLM_MODEL` identifies a Gemini model available to the configured credential.
3. Apply migrations `002_career_intelligence.sql`, `003_smart_job_discovery.sql`, and `004_advanced_features.sql`, in that order, on the intended branch.
4. Set `ENABLE_CAREER_INTELLIGENCE=true`.
5. Set `ENABLE_ADVANCED_FEATURES=true`.
6. Restart the backend.
7. Upload a resume, review it, and save an approved resume version.
8. Verify authenticated `GET /api/interviews/status` reports `enabled=true` and `ready=true`.
9. Test a small practice session, answer persistence, and structured evaluation.

`ENABLE_GMAIL` and Google OAuth credentials are not required for Interview Practice.

## 3. Career Analytics

**Current status:** Blocked by migrations `002`/`003` and the Job Discovery feature gate.

| Requirement | Finding |
|---|---|
| Data provider | Existing Neon PostgreSQL application data |
| External analytics provider | None |
| Database variable | `DATABASE_URL` |
| Database configured | Yes |
| New API key necessary | No |
| Direct analytics flag | None |
| Route readiness gate | `ENABLE_JOB_DISCOVERY=true` plus the complete migration `003` schema |
| Required migrations | `002`, then `003` |
| Optional interview metrics | Require migration `004` and `ENABLE_ADVANCED_FEATURES=true` |

### Activation steps

1. Keep the existing `DATABASE_URL` for runtime application traffic.
2. Apply migrations `002` and `003` on the intended Neon branch using a direct TLS migration connection.
3. Set `ENABLE_JOB_DISCOVERY=true`.
4. Restart the backend.
5. Verify authenticated `GET /api/analytics/career`.
6. Add application-tracker records to populate the funnel and conversion metrics.
7. Optionally apply migration `004` and set `ENABLE_ADVANCED_FEATURES=true` to include interview-practice scores.

The Career Analytics endpoint does not call Gemini or an external analytics API.

## Environment-variable inspection

| Variable | Present/configured |
|---|---|
| `DATABASE_URL` | Yes |
| `LLM_API_KEY` | Yes |
| `GEMINI_API_KEY` | No; not needed while `LLM_API_KEY` is configured |
| `LLM_MODEL` | Yes |
| `HIMALAYAS_API_KEY` | Yes |
| `JOB_PROVIDER` | Himalayas |
| `HIMALAYAS_API_BASE_URL` | Code default is the official jobs endpoint |
| `ENABLE_CAREER_INTELLIGENCE` | Not explicitly present; default is off |
| `ENABLE_JOB_DISCOVERY` | Not explicitly present; default is off |
| `ENABLE_ADVANCED_FEATURES` | Not explicitly present; default is off |

The backend loads settings from root `.env`, root `.env.local`, and `backend/.env`; process environment variables take precedence. Settings are loaded at process startup, so the backend must be restarted after changes.

## Database findings

The configured Neon connection passed `SELECT 1`. Read-only schema inspection found no complete or partial installation of migrations `002`, `003`, or `004` on that database.

The repository contains evidence that these migrations were previously verified on isolated development branches. That does not mean they are installed on the database currently referenced by `DATABASE_URL`. Production migration still requires backup/restore evidence and explicit approval.

## Conclusion

The existing Gemini, Himalayas, and Neon credentials are sufficient. No additional provider key is required for the requested features.

All three requested features are currently inactive because the configured database lacks their migrations and the relevant feature flags are off. No migration, billing activation, credential change, or database write was performed during this inspection.
