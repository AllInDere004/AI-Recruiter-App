# Staging deployment guide

This repository now includes non-root backend/frontend Dockerfiles, `docker-compose.staging.yml`, health endpoints, and CI. These files prepare a staging deployment; they do not deploy anything.

## Required environment names

Set secrets in the hosting secret store, never in Git. Required values include `DATABASE_URL`, `JWT_SECRET_KEY`, and `LLM_API_KEY` or `GEMINI_API_KEY`. Configure `ENVIRONMENT=staging`, explicit `CORS_ORIGINS`, explicit `ALLOWED_HOSTS`, and the public `NEXT_PUBLIC_API_URL` at frontend build time.

Enable `ENABLE_CAREER_INTELLIGENCE`, `ENABLE_JOB_DISCOVERY`, and `ENABLE_ADVANCED_FEATURES` only after migrations `002`, `003`, and `004` are verified in that environment. Gmail remains optional: leave `ENABLE_GMAIL=false` until its client ID, secret, HTTPS callback URI, and Fernet key are stored and an operator approves activation.

For production, set `ENVIRONMENT=production` and `FORCE_HTTPS=true`; startup rejects unsafe combinations. TLS should terminate at the selected ingress, with only trusted proxy addresses forwarded to Uvicorn in the final platform configuration.

## Promotion sequence

1. Resolve the frontend critical dependency audit.
2. Create a schema-only staging branch and use its direct, TLS-required connection for migrations.
3. Take and restore-test a production backup before any production migration approval request.
4. Apply migrations to staging, run `/live`, `/ready`, the complete backend suite, frontend build, and browser regressions.
5. Provision a staging admin through a database-owner change with an audit ticket. Do not add a public role-grant endpoint.
6. Configure OAuth with staging-only redirect URIs and test draft review without sending to real recipients.
7. Capture load, error-rate, log-redaction, alert, backup, and rollback evidence.
8. Request explicit approval separately for the production migration, deployment, Gmail activation, and any real email send.

Rollback is application-image rollback plus a forward database correction. Migration `004` is additive; its tables must not be dropped as an automated rollback.
