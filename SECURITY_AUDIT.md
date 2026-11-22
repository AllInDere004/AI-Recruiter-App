# Phase 4 security and privacy audit

Date: 2026-11-08

## Result

Backend dependency audit passes with no known vulnerabilities after replacing `python-jose` with PyJWT and upgrading `cryptography`. The frontend dependency audit is a release blocker: npm reports one critical, five high, and six moderate advisories in the current Next.js 14/Zod 3 lint and runtime tree. npm's available remediation is a breaking Next.js 16 and Zod 4 migration; it was not forced into this feature change without a dedicated compatibility pass.

## Controls implemented

- Server-side ownership checks cover interview sessions, questions, answers, evaluations, notification preferences, Gmail connections, and approved generated email records.
- Composite database foreign keys prevent cross-user relationship insertion even if an API check regresses.
- Admin access is deny-by-default and derived from active `user_roles` rows on the server. There is no client-controlled admin flag and no public role-provisioning endpoint.
- Gmail is disabled by default. OAuth uses state hashing, one-time state rows, PKCE, encrypted refresh tokens, and minimal send scope. Sending requires an approved immutable email version, exact reviewed content, explicit confirmation, and an idempotency key.
- Gemini input is marked untrusted, structured output is validated, evidence quotes must be exact answer substrings, and AI scores are labelled as practice estimates.
- Validation responses omit raw client input. Database exceptions omit SQL and parameters. Provider status reports expose booleans, never credential values.
- Explicit CORS origins, trusted hosts, HTTPS production validation, HSTS when HTTPS is forced, frame denial, MIME sniffing prevention, restrictive browser permissions, referrer controls, and private API caching defaults are configured.
- Production startup rejects a short/default JWT key, wildcard hosts/CORS, non-HTTPS origins, non-PostgreSQL storage, disabled HTTPS, and incomplete enabled Gmail settings.
- CI rejects tracked `.env` files and common private-key/API-key patterns and runs backend/frontend advisory audits.

## Verification

- `python -m pip_audit -r backend/requirements.txt`: no known vulnerabilities.
- `npm audit --audit-level=critical`: failed as intended with 12 advisories; production release is blocked.
- Security/integration tests cover cross-user access, stale versions, prompt injection, duplicate AI questions, OAuth replay, token encryption, explicit Gmail consent, send idempotency, admin denial, trusted-host rejection, and security headers.
- No real email was sent. No Google OAuth authorization or paid service was enabled.

## Open risks

1. Upgrade and regression-test Next.js, React, Zod, PostCSS, and ESLint before production.
2. Process-local rate limits do not coordinate across multiple workers. Use a reviewed shared limiter before horizontal scaling.
3. Add centralized redacted logs, alerting, retention/deletion policy automation, and incident response ownership in the selected hosting platform.
4. Run DAST and authenticated penetration testing against staging after deployment.
5. Provision the first admin role through an audited database-owner procedure; never expose role assignment to ordinary users.
