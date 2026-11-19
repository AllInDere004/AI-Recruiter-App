# Production migration and recovery plan

This is a runbook, not authorization. Do not execute any production write, backup,
restore, migration, feature-flag change, or deployment without explicit approval.

## Preconditions and approval gates

1. Freeze the release artifact and record its Git commit and dependency lockfiles.
2. Confirm the selected Neon branch and direct (non-pooled) migration endpoint. Keep
   the pooled endpoint for normal application traffic. Require TLS.
3. Confirm `SELECT 1`, the expected database name, and the existing ten-table schema.
4. Confirm no partial installation of migrations `002`, `003`, or `004` exists.
5. Configure a production-grade JWT secret, HTTPS, explicit CORS origins/hosts, and
   monitoring. Keep Gmail disabled unless its separate OAuth/send approvals exist.
6. Configure `HIMALAYAS_API_KEY` before requiring live provider search. Do not put the
   key in source control or any `NEXT_PUBLIC_*` variable.
7. Obtain explicit approval for the production backup/restore exercise, migration,
   deployment, and later feature-flag activation.

## Backup and recovery evidence

1. Record the migration start time, current production branch/endpoint identifiers,
   migration operator, release commit, and current row counts.
2. Create a Neon restore point or snapshot within the project's retention policy.
   Record its identifier and timestamp without recording credentials.
3. Create an encrypted logical backup with `pg_dump` through a direct TLS connection
   to approved restricted storage. Treat the backup as sensitive because it may
   contain resumes and other personal data.
4. Restore to a separate temporary branch and run `SELECT 1`, table/row-count checks,
   authentication smoke tests, and representative owned-data reads. Record recovery
   duration and the restore point used. Delete the temporary restore branch only
   after evidence is approved.
5. Set the recovery objective: schema failures use transaction rollback; a later
   application incident first disables the flags and rolls back the application.
   Restoring production from a snapshot is a separate destructive action requiring
   approval and reconciliation of writes made after the restore point.

## Migration execution

1. Put application deployments on hold; keep the three feature flags false.
2. Connect through the direct TLS endpoint with a least-privileged migration role.
3. Apply, one transaction at a time and in this exact order:
   `002_career_intelligence.sql`, `003_smart_job_discovery.sql`, then
   `004_advanced_features.sql`.
4. Stop on the first error. Capture the migration name and PostgreSQL SQLSTATE, but
   never log connection strings or secrets.
5. Verify all 21 new tables, their indexes, named checks, foreign keys, composite
   user-ownership constraints, and model metadata. Confirm the original ten tables
   are unchanged.
6. Run authenticated API, authorization, ownership, browser, and regression smoke
   tests while all feature flags remain false.

## Controlled activation

1. Enable `ENABLE_CAREER_INTELLIGENCE`, restart, and verify its status and owned
   resume-version workflow.
2. Enable `ENABLE_JOB_DISCOVERY`, restart, and verify provider status, one bounded
   Himalayas search, reviewed import, saved job, and application tracker workflow.
3. Enable `ENABLE_ADVANCED_FEATURES`, restart, and verify interview status, one
   bounded Gemini practice session, evaluation/history, and real-data analytics.
4. Monitor database errors, latency, Gemini/Himalayas error rates, rate limiting, and
   authorization failures between each step. Roll back flags before escalating.

## Non-destructive rollback order

1. Set all three flags false and restart the application.
2. Roll back the application artifact if necessary.
3. Leave additive tables in place; do not drop tables or delete records as a routine
   rollback.
4. If data integrity is compromised, stop writes and request explicit approval for
   point-in-time restore. Reconcile post-restore writes before reopening traffic.
