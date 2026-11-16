# Phase 2 implementation and verification report

Date: 2026-11-06 (Asia/Calcutta)
Branch: feature/phase-2-career-intelligence
Source baseline: 8c42636

## Delivery status

Phase 2 is implemented and verified in isolated environments. New persistence is NOT activated on production. The production database still has its original ten tables; SELECT 1 succeeds; ENABLE_CAREER_INTELLIGENCE remains false.

Production activation requires a verified database backup/restore checkpoint and explicit approval of backend/migrations/002_career_intelligence.sql. No production schema or record changes were executed. A production backup has not been taken; pg_dump/psql were not available in this environment. A Git baseline and schema-only development branch are not data backups.

Existing uncommitted .gitignore changes, PHASE1_AUDIT.md, local skills, and editor files were preserved. No environment values, API keys, database URLs, tokens, or private resume content are included in this report. Code remains reviewable in the feature branch working tree.

## Audit and architecture

The actual application uses Next.js 14.2.35, React 18, TypeScript, Tailwind, GSAP, npm, FastAPI, SQLAlchemy, psycopg2, JWT bearer authentication, Google Gen AI, PyMuPDF, and local MiniLM.

The active frontend uses FastAPI and users/profiles/jobs/drafts. The separate Next.js API and recruiter-prefixed table family remain preserved. No table was renamed, merged, reset, truncated, or deleted.

PHASE1_AUDIT.md records an audit checkpoint rather than a completed hardening implementation. Phase 2 accounts for that reality: implicit production DDL, sensitive validation reflection, safe DB exceptions, and AI usage controls were addressed as prerequisites. Existing JWT strength, localStorage token architecture, login throttling, and the duplicate legacy API remain separate hardening work.

The initial Phase 2 audit and proposed file/migration plan were presented before significant modifications and are saved in PHASE2_PLAN.md.

## Features delivered

| Area | Implementation and preservation |
| --- | --- |
| Resume intelligence | Optional technical/soft skills, certifications, projects, internships, employment history, detailed education/dates, achievements, evidence and uncertainty. Legacy profile fields remain supported. |
| Source evidence | Server-computed verification against complete safe source lines. Model-provided verification/confidence never grants credit. Forged quotes, negation stripping, instruction-like spans, and numeric/skill substring confusion are rejected. |
| Upload provenance | Bounded PDF validation, sanitized filename, MIME, byte size, SHA-256. No PDF bytes or local upload paths are stored. Page count/layout are explicitly unavailable. |
| Job intelligence | Required/preferred skills, location, employment type, experience/education requirements, qualifications, source evidence, and ambiguity. Source-stated preferences correct mistaken model classification. Existing keys remain compatible. |
| Matching | Separate deterministic career engine, configurable five-category weights, evidence-linked classifications, mandatory gaps, stable algorithm/input versions. Existing /api/match/compare MiniLM behavior is preserved. |
| Gaps | Required/preferred/unclear classifications, prioritized practical activities, optional Gemini learning guidance. Saved within owned versioned reports. |
| ATS | Extracted-text parseability, contact and section checks, readable-text signals and separate job-keyword relevance. No employer acceptance guarantee or invented PDF layout assessment. |
| Tailoring | Gemini selects/reorders verified evidence IDs; the server renders complete source wording and retains grouped employer/education/project facts. Original resume is unchanged. Historical before/after comparison uses the exact owned source version. |
| Documents | Tailored resumes, role-specific cover letters, versioned application/referral/follow-up/internship emails, three new tones, subject suggestions, editing, regeneration, explicit review and approval. Nothing is sent automatically. |
| Versioning | Immutable resume/document content histories, server-derived ownership, original-source deduplication, input/policy/model references, stale sibling-edit conflicts. User edits are labeled separately and lose old AI evidence IDs. |
| Export | Authenticated approved-only PDF/DOCX downloads, generated in memory, private/no-store headers, constant safe filenames, escaped content, no public files or credential-bearing URLs. |
| Frontend | New panels inside existing profile/outreach/dashboard/tracker/draft pages; existing shell/sidebar/styles/motion untouched. Loading/error/retry/empty/success states, submission guards and stale-response checks in new panels. |
| Security | No PostgreSQL DDL at startup; sanitized validation/DB errors; hidden sensitive settings repr; bound queries; cross-user rejection; upload limits; bounded per-user AI throttles. |
| Tooling | Noninteractive ESLint configured for the existing Next version. No framework/authentication/database architecture replacement. |

## Scoring policy

Algorithm: career-evidence-v1.

Default weights:
- Required skills: 40%.
- Preferred skills: 15%.
- Experience/projects: 20%.
- Education: 10%.
- Role alignment: 15%.

Weights renormalize only when the JOB has no requirements in a category. Missing candidate evidence remains zero-credit. Exact matches and curated aliases receive skill credit; related skills do not imply equivalence. Role alignment is separately labeled lexical coverage. Qualifications use conservative literal evidence rather than inferred degree equivalence or inferred years of experience. Mandatory gaps remain visible independently of the total score.

Scores are compatibility estimates, not hiring probabilities, eligibility determinations, or guarantees. Source-backed means supported by the candidate-provided resume, not independently verified by a third party.

## Storage and migration assessment

Three additive tables:
- resume_versions: reviewed/extracted snapshots, owner/history, source provenance and immutable structured data.
- career_reports: saved match/gap/ATS results, algorithm version and input fingerprints, owner-scoped deduplication.
- generation_versions: immutable document lineage/revisions, review state, source/job/draft links and model/content metadata.

Existing profiles.parsed_data and jobs.extracted_skills JSON are extended without changing existing columns. Original resume text is stored once per distinct source and resolved through owner-scoped historical snapshots rather than copied on every review/edit. Prompts and original PDF binaries are not persisted.

New table CHECK/unique/FK constraints protect valid kinds/revisions, same-owner resume references, and one child per document parent. Existing job/draft ownership is verified server-side; the original parent tables were not altered to add composite owner keys. Proposed broader legacy ownership/index improvements remain separate from this additive migration.

The development verification script refuses production/default branches and excludes the configured production endpoint before DDL. It captures credentials only in memory and never prints CLI credential output.

Development branch:
- Name: phase2-career-intelligence-20261106.
- ID: br-jolly-boat-az77y9f1.
- Schema-only; no private production rows copied.
- Expires: 2026-11-07T11:06:21Z (2026-11-07 16:36:21 IST).
- Existing cloud plan unchanged; minimum compute used.

PHASE2_MIGRATION_TEST.md contains the metadata-only execution report. Migration application, all ten original schemas, three new schemas, indexes, unique/CHECK/FK constraints, SELECT 1/TLS, synthetic persistence, cross-user FK rejection, immutable lineage and stale sibling conflicts passed. Synthetic test writes were rolled back and original schemas were unchanged.

Application startup never applies this SQL file. The production feature flag remains false; readiness checks are read-only.

## Gemini integration

The configured Gemini model was checked for availability without changing it. Synthetic live checks passed for:
1. Structured advanced resume extraction.
2. Structured job intelligence.
3. Evidence-only cover-letter generation.

An actual SDK additionalProperties conversion failure was identified and fixed by using native response_json_schema with strict Pydantic validation after response parsing. See [official SDK schema documentation](https://googleapis.github.io/python-genai/).

The client retains LLM_API_KEY/GEMINI_API_KEY aliases, explicit v1beta and server-side credentials. It uses a 45-second per-attempt timeout, two total attempts only for selected 5xx errors, no automatic model fallback, no quota/auth/model retries, and no timeout retries that might duplicate a completed paid request. SDK retries are disabled to make attempts and logging behavior explicit.

400, 401/403, 404, 429, 5xx, empty output, malformed JSON, schema mismatch, and installed HTTP-transport timeout paths have sanitized handling/tests. Provider authentication failures never become an application-user 401 logout.

No paid API or billing setting was introduced or enabled. Live smoke calls used only synthetic text, the existing configured provider/model, and no database writes.

## Actual commands and results

| Check | Executed command/method | Result |
| --- | --- | --- |
| Baseline backend | From backend: ..\\.venv\\Scripts\\python.exe -B -m unittest discover -s tests -v | 81 passed |
| Baseline types | From frontend: npx tsc --noEmit --incremental false | Passed |
| Baseline build | Root npm run build, NEXT_DIST_DIR=.next-phase2-baseline | Passed |
| Baseline lint | Root npm run lint, CI=1 | Exit 1: interactive setup, ESLint unconfigured |
| Final backend | From backend: python -B -m unittest discover -s tests -q using project virtualenv | 159 passed |
| Final types | From frontend: npx tsc --noEmit --incremental false | Passed |
| Final lint | Root npm run lint | Passed, zero warnings/errors |
| Final build | Root npm run build, NEXT_DIST_DIR=.next-phase2-verify | Passed, all 12 static pages generated |
| Original browser workflow | Root npm run test:fastapi:browser, virtualenv prepended to PATH | Passed |
| New career browser workflow | Root npm run test:career:browser | Passed, including final provenance/source/export run |
| Development migration | backend/scripts/verify_phase2_development.py on explicit schema-only development branch | Passed |
| Live Gemini | Inline synthetic SDK/extraction/generation smoke script | Passed after native JSON Schema fix |
| Production safeguard | Read-only existing client: SELECT 1 and table catalog | Passed; ten tables, no Phase 2 tables, feature false |
| Diff validation | git diff --check | Passed |
| Dependency audit | npm audit --json | 12 findings: 1 critical, 5 high, 6 moderate; unresolved |

The original browser suite verified signup/login, invalid credentials, onboarding, PDF rejection/success, profile review/save/reload, job analysis errors, MiniLM matching, generated warnings, draft editing, tracker status, deletion, expiry, logout and re-login.

The new browser suite verified reviewed immutable resume versions, saved ATS/match/gap/learning reports, cover-letter editing/regeneration/approval, authenticated PDF/DOCX readability, exact historical tailored-source comparison, version history after refresh/re-login, real dashboard summaries, no browser runtime errors, and mobile 390px layout without horizontal overflow.

Browser tests used temporary SQLite and mocked Gemini on localhost ports 8002/3001. No browser test wrote to production. Unit/API tests cover cross-user read/create/edit/export, unauthenticated access, version conflicts, source privacy, invalid/oversized PDFs, forged/negated evidence, prompt injection, error sanitization and usage quotas. Final quota refinements were verified in the 159-test backend suite.

One earlier targeted test command was declined and was not counted as an executed test. Subsequent full-suite runs used explicit approval. A first live schema attempt failed safely; the final successful live checks followed the SDK fix. Test-server interrupt exit codes during cleanup are not test failures.

Both isolated test servers were stopped. Test-only Next.js TypeScript include entries were removed; pre-existing include entries remain.

## Reproducing isolated browser checks

From backend in a dedicated PowerShell terminal:

~~~powershell
$env:TEST_CAREER_INTELLIGENCE='1'
..\\.venv\\Scripts\\python.exe -B -c "import runpy; runpy.run_path('tests/frontend_server.py', run_name='__main__')"
~~~

From repository root in another terminal:

~~~powershell
$env:NEXT_DIST_DIR='.next-career-local'
$env:NEXT_PUBLIC_API_URL='http://127.0.0.1:8002'
npm run dev -- --port 3001
~~~

From repository root with the project virtualenv on PATH:

~~~powershell
npm run test:fastapi:browser
npm run test:career:browser
~~~

Do not substitute production URLs. The new browser suite blocks nonlocal API destinations. The old test:neon scripts target the legacy API and were not executed.

## Remaining limitations and activation boundary

1. Production migration/activation is pending verified backup/restore and explicit approval. No backup is claimed. Do not enable the feature against production before that checkpoint.
2. Tailoring is intentionally extractive/reordering; it does not freely rewrite candidate facts. Cover-letter/email wording is conservative around selected evidence; user-authored edits require explicit review.
3. Evidence/negation and requirement matching are conservative English heuristics with curated aliases; they are not semantic proof or external verification.
4. ATS assessment is text-based. Original PDF visual layout/font metadata is not retained, no OCR is added, and no employer ATS guarantee is made.
5. PDF readability and DOCX ZIP/XML validity were tested; no desktop Microsoft Word interoperability session was run.
6. AI throttles are per server process: existing Gemini endpoints default to 30 requests/minute/user, new intelligence AI requests default to 6. Multi-instance deployments need shared quota enforcement.
7. The dependency audit remains open. Next and Zod versions are unchanged from baseline; the compatible ESLint tooling adds its development dependency chain. No audit fix --force or framework migration was performed. For example, [Next Windows-hosted RCE advisory](https://github.com/advisories/GHSA-p293-qw3h-jr36) and [Zod collection validation advisory](https://github.com/advisories/GHSA-mrhx-c7xc-m3w5) need a separately tested dependency upgrade. This is not a production security sign-off.
8. Pre-existing JWT strength/rotation, client-side-only logout revocation, localStorage session risk, login/signup throttling and duplicate legacy API exposure remain documented in PHASE1_AUDIT.md. Credentials were not rotated and working sessions were preserved.
9. Existing-table composite owner constraints and historical-query indexes were not applied; all ownership in current/new APIs is checked server-side.
10. The development branch expires automatically; it is a migration test environment, not a durable production backup.

## Changed files

The following list excludes pre-existing .gitignore/audit/editor/skills work and generated build outputs.
- `backend/README.md`
- `backend/app/api/email.py`
- `backend/app/api/intelligence.py`
- `backend/app/api/jobs.py`
- `backend/app/api/profile.py`
- `backend/app/api/resume.py`
- `backend/app/config.py`
- `backend/app/database.py`
- `backend/app/main.py`
- `backend/app/ml/skill_taxonomy.py`
- `backend/app/models/intelligence.py`
- `backend/app/prompts/extract_profile.txt`
- `backend/app/prompts/job_analysis.txt`
- `backend/app/schemas/profile.py`
- `backend/app/services/ai_usage.py`
- `backend/app/services/career_intelligence.py`
- `backend/app/services/career_repository.py`
- `backend/app/services/document_generation.py`
- `backend/app/services/evidence.py`
- `backend/app/services/job_analyzer.py`
- `backend/app/services/llm_client.py`
- `backend/app/services/profile_extractor.py`
- `backend/migrations/002_career_intelligence.sql`
- `backend/scripts/verify_phase2_development.py`
- `backend/tests/frontend_server.py`
- `backend/tests/test_ai_usage.py`
- `backend/tests/test_career_intelligence.py`
- `backend/tests/test_document_generation.py`
- `backend/tests/test_intelligence_api.py`
- `backend/tests/test_llm_reliability.py`
- `backend/tests/test_phase2_migrations.py`
- `frontend/.eslintrc.json`
- `frontend/app/dashboard/page.tsx`
- `frontend/app/drafts/[id]/page.tsx`
- `frontend/app/new-email/page.tsx`
- `frontend/app/profile/page.tsx`
- `frontend/app/tracker/page.tsx`
- `frontend/components/CareerDocuments.tsx`
- `frontend/components/CareerIntelligence.tsx`
- `frontend/components/ProfileEditor.tsx`
- `frontend/components/SituationPicker.tsx`
- `frontend/components/TonePicker.tsx`
- `frontend/lib/api.ts`
- `frontend/lib/presenters.ts`
- `frontend/package-lock.json`
- `frontend/package.json`
- `frontend/scripts/test-career-browser.cjs`
- `frontend/types/index.ts`
- `package.json`
- `PHASE2_PLAN.md`
- `PHASE2_MIGRATION_TEST.md`
- `PHASE2_REPORT.md`
