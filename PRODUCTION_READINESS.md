# Production readiness decision

Date: 2026-11-10
Decision: **Not ready for production deployment**

## Verified

- Phase 4 application features are implemented behind opt-in flags.
- Full backend regression: 189 tests and 36 subtests pass.
- Frontend TypeScript, lint, and optimized production build pass.
- Isolated Phase 1, Career Intelligence, Job Discovery/application/analytics, and Phase 4 interview browser flows pass against temporary data and mocked providers.
- Neon migrations `002` through `004` pass in order with `SELECT 1`, TLS/direct-host validation, complete model/schema parity, indexes, named checks, ownership constraints, synthetic data checks, and full rollback on schema-only branch `phase4-full-activation-20261110` (`br-round-surf-az9wjgvn`). Production was excluded.
- Backend dependency audit reports no known vulnerabilities.
- No credentials were printed or added to Git, no real email was sent, and no deployment occurred.

## Release blockers

- npm reports a critical Next.js advisory and additional high/moderate advisories. A tested Next.js 16/Zod 4 upgrade is required.
- Migration `004` has not been applied to production, as required. A restore-tested backup and explicit approval are absent.
- Staging has not been deployed, load-tested, penetration-tested, or observed under representative traffic.
- Docker is not installed in this workstation environment, so the prepared images were not locally built; CI/staging must build and smoke-test them.
- Real Gemini validation was not run during the isolated regression; it requires the operator's configured key/quota and must avoid storing test personal data.
- Gmail OAuth credentials/consent are not configured and no real send was approved.
- No initial admin role has been provisioned through an audited owner procedure.
- The currently loaded development JWT key is below PyJWT's recommended HMAC length; rotate it to a unique 32+ byte value before staging and invalidate old sessions deliberately.
- Git author identity is unset, so the safe Phase 1–3 checkpoint remains staged rather than committed.
- Distributed rate limiting, production monitoring/alerting, retention automation, and incident-response ownership remain environment work.

## Deployment checklist

- [ ] Upgrade the advisory-affected frontend dependency tree; rerun audit, build, and all browser tests.
- [ ] Configure Git author identity and approve the baseline/Phase 4 commit scope.
- [ ] Deploy to staging with environment-specific Neon and Gemini credentials.
- [ ] Apply `002`–`004` to staging using a direct TLS connection; archive sanitized verification evidence.
- [ ] Verify backup restoration and document recovery time/data-loss objectives.
- [ ] Run regression, DAST, load, accessibility, and privacy-retention tests in staging.
- [ ] Configure explicit production CORS origins/hosts, strong JWT key, HTTPS/HSTS, log redaction, alerts, and secret rotation.
- [ ] Provision and verify the initial admin role through an audited database-owner change.
- [ ] Obtain separate approval for production migration and deployment.
- [ ] Keep Gmail disabled until OAuth review; obtain explicit approval for every real-email test campaign.
