# Production activation readiness — 2026-11-10

## Decision

**NO-GO for full production activation yet; GO for the production migration approval
gate.** Production is unchanged. The production-like migration rehearsal and the
snapshot restore verification both passed. Full activation remains blocked until the
deployed production secret store is verified and the production migrations,
deployment, restart, and staged feature flags receive explicit approval.

## Exact production identity

- Neon project: `divine-dust-28314320`
- Branch: `production`
- Branch ID: `br-summer-bread-az2p9coe`
- Default/primary branch: yes
- Compute endpoint ID: `ep-nameless-art-azbkpc4v`
- Database: `neondb`
- Region: `aws-ap-southeast-1`
- Backend URL mapping: exact endpoint match
- Runtime URL: pooled, `sslmode=require`
- Migration connection requirement: direct/unpooled, TLS required
- Connectivity: `SELECT 1` passed

No connection string, password, API key, or token is included in this report.

## Production inventory and migration history

The public schema currently contains 10 tables:

`drafts`, `jobs`, `profiles`, `recruiter_drafts`, `recruiter_jobs`,
`recruiter_migrations`, `recruiter_profiles`, `recruiter_sessions`,
`recruiter_users`, and `users`.

The database contains 8 application rows across the populated tables. Read-only
counts were captured for before/after comparison without reading row contents.
There were no waiting locks during the audit.

`recruiter_migrations` contains exactly one entry:

- `001_recruiter.sql`, applied `2026-11-05T16:52:19.507698Z`

Migrations 002, 003, and 004 are not present in production. These backend SQL files
do not currently insert their names into `recruiter_migrations`; production release
bookkeeping must therefore be explicitly approved and recorded after schema checks.

## Backup and restore evidence

Snapshot created successfully:

- Snapshot ID: `snap-small-recipe-az6nfgwk`
- Name: `pre-phase-234-production-20261110`
- Source: production branch `br-summer-bread-az2p9coe`
- Created: `2026-11-10T11:37:44Z`
- Expires: `2026-11-17T18:00:00Z`

The first isolated restore attempt was blocked by the root-branch quota. After
explicit approval, the exact temporary branch
`phase4-full-activation-20261110` (`br-round-surf-az9wjgvn`) was verified as
non-production, schema-only, childless, and empty across all 31 tables. Its migration
evidence was confirmed on disk before that branch—and only that branch—was deleted.

Snapshot restore then passed without `--finalize`:

- Inspection branch: `production-snapshot-inspection-20261110`
- Inspection branch ID: `br-little-sky-az8zq4sx`
- State: ready; restore status: restored
- Source snapshot: `snap-small-recipe-az6nfgwk`
- Default/primary/protected: no/no/no
- Production endpoint swap/finalization: not performed
- Database: `neondb`
- `SELECT 1`: passed on production and restored branch
- Public tables: 10 on both branches; exact table lists match
- Per-table row counts: exact match
- Schema metadata fingerprint: exact match
- Migration history: exact match (`001_recruiter.sql`)
- Connection: direct endpoint, `sslmode=require`, channel binding required
- libpq TLS session: active

The restored counts were `drafts=2`, `jobs=2`, `profiles=1`,
`recruiter_migrations=1`, `users=1`, and zero for the five remaining legacy tables.
No row contents were read or printed. A final read-only production check confirmed
that production still has 10 tables, migrations 002–004 remain absent, Job Discovery
remains disabled, and `production` is still the default/primary branch.

As a separate data-preservation check, an isolated child of production was created:

- Branch: `production-migration-rehearsal-20261110`
- Branch ID: `br-lucky-moon-azq5607n`
- Parent LSN: `0/1F0FC98`
- Parent timestamp: `2026-11-10T11:37:35Z`
- Expires: `2026-11-17T18:00:00Z`

On that branch, 002, 003, and 004 completed in 0.110 s, 0.161 s, and 0.161 s.
All 10 original table definitions and row counts were unchanged. All 21 new tables
were created empty; 21 ownership foreign keys and 74 total indexes/constraint indexes
on new tables were reflected successfully. Production endpoint exclusion and direct
TLS connection checks passed. Full machine-readable evidence is in
`PRODUCTION_MIGRATION_REHEARSAL.md`.

## Migration compatibility and risk

| Migration | Effect | Existing-data impact | Lock/rollback assessment |
|---|---|---|---|
| 002 | 3 tables for resume versions, career reports, and generated-document lineage | No update/backfill; references existing `users`, `profiles`, `jobs`, and `drafts` | One transaction. Inline foreign keys briefly take `SHARE ROW EXCLUSIVE` locks on referenced tables. Failure rolls back 002 only. |
| 003 | 8 tables for external listings, saved jobs, applications, events, reminders, notifications, and recommendations | No update/backfill; depends on 002 and existing `users`/`jobs` | One transaction. Brief FK locks on existing/recently created tables. Failure rolls back 003 only; a committed 002 remains. |
| 004 | 10 tables for interviews, notification preferences, Gmail metadata, roles, and admin audit | No update/backfill; depends on 002 and 003 | One transaction. Brief FK locks, primarily on `users`, `jobs`, `resume_versions`, and `generation_versions`. Failure rolls back 004 only. |

All three files are additive: no `ALTER TABLE`, `DROP`, `TRUNCATE`, `DELETE`,
`UPDATE`, or data backfill. Standard indexes are created only on new empty tables,
so index-build duration and write blocking are minimal. PostgreSQL documents that
adding a foreign key takes `SHARE ROW EXCLUSIVE` on its referenced table and that
non-concurrent indexes block writes to the table being indexed; here those indexes
target only newly created empty tables.

The three-file sequence is not globally atomic because each file has its own
`BEGIN`/`COMMIT`. If a later file fails, keep feature flags false, inspect the schema,
fix the cause, and resume from the first unapplied file. Do not rerun an already
committed file because the DDL intentionally omits `IF NOT EXISTS`.

## Credentials and feature flags

- Local `backend/.env`: `HIMALAYAS_API_KEY` configured — **yes**
- Provider selected by the backend: `himalayas`
- Local backend setting: `ENVIRONMENT=development`
- Deployed production secret store: **not identifiable from this repository**

Therefore the actual hosted production environment's key cannot be certified from
local files alone. Before activation, an operator must confirm the key name exists in
the deployment platform and run `/api/discovery/status`; the value must never be
printed.

Prepared, but deliberately not loaded or enabled:

```ini
ENABLE_CAREER_INTELLIGENCE=true
ENABLE_JOB_DISCOVERY=true
ENABLE_ADVANCED_FEATURES=true
```

The values are stored in `backend/feature-activation.production.ini`. The settings
loader does not read this file automatically.

## Exact approved migration runbook

Run these only after explicit approval, from the repository root, during a low-write
window. Inject the direct URL from the production secret store without printing it.

```powershell
$env:DATABASE_URL_UNPOOLED = '<direct production URL injected from secret storage>'
$env:PGOPTIONS = '-c lock_timeout=5s -c statement_timeout=120s'

psql "$env:DATABASE_URL_UNPOOLED" -v ON_ERROR_STOP=1 -c "SELECT current_database(), pg_is_in_recovery();"
psql "$env:DATABASE_URL_UNPOOLED" -v ON_ERROR_STOP=1 -c "SELECT count(*) AS waiting_locks FROM pg_locks WHERE NOT granted;"

psql "$env:DATABASE_URL_UNPOOLED" -v ON_ERROR_STOP=1 -f backend/migrations/002_career_intelligence.sql
psql "$env:DATABASE_URL_UNPOOLED" -v ON_ERROR_STOP=1 -f backend/migrations/003_smart_job_discovery.sql
psql "$env:DATABASE_URL_UNPOOLED" -v ON_ERROR_STOP=1 -f backend/migrations/004_advanced_features.sql

psql "$env:DATABASE_URL_UNPOOLED" -v ON_ERROR_STOP=1 -c "SELECT count(*) FROM pg_catalog.pg_tables WHERE schemaname='public';"
psql "$env:DATABASE_URL_UNPOOLED" -v ON_ERROR_STOP=1 -c "SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname='public' ORDER BY tablename;"
```

Expected result: public-table count increases from 10 to 31; all 21 new tables are
empty; existing row counts remain unchanged. Flags stay false through this step.

After verifying all 31 tables and only with approval to update the existing ledger:

```powershell
psql "$env:DATABASE_URL_UNPOOLED" -v ON_ERROR_STOP=1 -c "INSERT INTO recruiter_migrations(name) VALUES ('002_career_intelligence.sql'),('003_smart_job_discovery.sql'),('004_advanced_features.sql') ON CONFLICT (name) DO NOTHING;"
```

## Recovery procedure

1. Keep the three flags false during migration. If an application check fails, no
   feature traffic reaches the new tables.
2. Roll application code back first and keep the additive tables in place. This is
   the safest recovery because the migrations do not alter existing tables.
3. Do not drop the 21 tables after users have written data. A DDL rollback would lose
   new feature data and is intentionally not prepared.
4. For catastrophic recovery, freeze writes, take a second snapshot of the current
   state, restore the pre-migration snapshot to a preview branch, validate counts and
   authentication, and reconcile post-snapshot writes before any endpoint swap.
5. Snapshot finalization changes the branch behind the production endpoint and must
   be separately approved:

```powershell
neon snapshots restore snap-small-recipe-az6nfgwk --project-id divine-dust-28314320 --target-branch production
# Validate the returned preview branch. Do not finalize until reconciliation is complete.
neon snapshots finalize <preview-branch-id> --project-id divine-dust-28314320
```

Restoring the snapshot without reconciling newer writes would discard changes made
after `2026-11-10T11:37:44Z`; it is a last-resort operation, not the normal rollback.

## Production smoke-test plan

Run with a dedicated test user; never use another user's records.

1. **Pre-activation:** `/live`, `/ready`, sign-up/sign-in/sign-out, token expiry,
   unauthorized-route rejection, profile read/update, resume upload/parse, job analysis,
   draft creation/edit, and the existing tracker.
2. **Career Intelligence:** enable only `ENABLE_CAREER_INTELLIGENCE`; create/select a
   resume version, run match/gap/ATS analysis, verify history and user ownership, then
   disable on any error.
3. **Job Discovery:** enable only `ENABLE_JOB_DISCOVERY`; verify status reports
   Himalayas configured without a key value, run one bounded real search, exercise
   filters/empty results/provider error handling, save/bookmark/import a job, calculate
   resume matching, create an application, and update tracking status.
4. **Advanced Features:** enable `ENABLE_ADVANCED_FEATURES`; create technical, HR,
   behavioral, and project interview sessions, select a resume, submit an answer,
   verify Gemini feedback/scores/history, and confirm career analytics reflects real
   application/interview metrics.
5. **Security/regression:** test cross-user IDs return 404/403, admin routes reject
   non-admins server-side, Gmail remains disabled, no email is sent, logs contain no
   tokens/keys/resume text, and all Phase 1–3 browser checks still pass.
6. **Operational:** inspect latency/error rates and DB locks after each flag. Roll back
   the last flag immediately if its smoke test fails.

## Tests executed in this readiness pass

- Read-only production `SELECT 1`: passed
- Production inventory/history/lock audit: passed
- Production-data child branch migration rehearsal: passed
- Migration/config regression suite: 13 passed
- Snapshot creation: passed
- Snapshot preview restore and direct-TLS verification: passed
- Production migrations, flags, deployment, restart: not performed

## Approvals still required

1. Confirm `HIMALAYAS_API_KEY` exists in the actual deployment platform's production
   secret store.
2. Approve production migrations 002–004 and the three migration-ledger entries.
3. Approve deployment/restart and staged feature-flag activation after smoke tests.

The backup/restore gate is satisfied. No production change should proceed until the
remaining approvals above are granted.

## References

- [Neon snapshot restore behavior](https://neon.com/blog/announcing-neon-snapshots-a-smoother-path-to-recovery)
- [Neon point-in-time branch recovery](https://neon.com/blog/point-in-time-recovery)
- [PostgreSQL CREATE TABLE / foreign-key locks](https://www.postgresql.org/docs/current/sql-createtable.html)
- [PostgreSQL CREATE INDEX locking](https://www.postgresql.org/docs/current/sql-createindex.html)
