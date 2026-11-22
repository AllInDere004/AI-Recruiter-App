# Phase 2 audit and implementation plan

Date: 2026-11-06, Asia/Calcutta. Branch: feature/phase-2-career-intelligence.

## Baseline before implementation
The actual stack remains Next.js 14.2.35/React 18/TypeScript/Tailwind/GSAP; FastAPI/SQLAlchemy/psycopg2; JWT bearer authentication; Google Gen AI SDK; PyMuPDF; local MiniLM. Existing frontend calls FastAPI, not the separate legacy Next API.
The previous Phase 1 artifact is an audit checkpoint, not a completed hardening implementation. Preserve its unresolved findings as prerequisites rather than claiming them fixed.

Executed baseline: 81 backend tests passed; TypeScript passed; production build passed; lint exited 1 because ESLint is unconfigured. The prior isolated browser run passed; a fresh preservation run will follow integration.

Current active tables: users, profiles, jobs, drafts. Preserve these and all six recruiter-prefixed/migration tables. Resume and job JSON can grow additively without changing those columns.

## Planned changes and boundaries
1. Add evidence-aware optional resume/job fields, strict Gemini response schemas, conservative skill aliases, deterministic matching, gaps, and ATS checks.
2. Keep the existing match/compare endpoint and its MiniLM scoring unchanged. New reports use configurable 40/15/20/10/15 weights, normalized only for absent job categories.
3. Add resume_versions, career_reports, generation_versions through a reviewed additive SQL proposal. No production DDL, table merge, rename, reset, or backfill.
4. Ordinary PostgreSQL startup must run no DDL before new metadata is registered. Feature ENABLE_CAREER_INTELLIGENCE defaults false and readiness is checked read-only. Existing workflows continue while production migration is pending.
5. New owner-scoped endpoints under /api/intelligence provide snapshots/review, saved reports, generation history, approval, and authorized in-memory PDF/DOCX export.
6. Source-grounded generation selects verified evidence conservatively, preserves original resume text and factual details, and requires review. Documents are never sent automatically.
7. Add panels within existing profile, outreach, dashboard, and tracker pages. Preserve layout, sidebar, styles, responsive behavior, and motion.
8. Classify Gemini errors safely, bound retries/timeouts, retain key aliases and configured model. Never switch models or enable billing automatically.
9. Test pure logic, malformed/untrusted AI outputs, ownership, append-only history, exports, gating, original workflows, and new browser workflows.

## Proposed files
- Existing schemas/profile.py, profile_extractor.py, job_analyzer.py and prompts: backward-compatible intelligence fields.
- New services/evidence.py, ml/skill_taxonomy.py, services/career_intelligence.py: deterministic evidence/scoring/ATS.
- New models/intelligence.py, api/intelligence.py, persistence helpers and backend/migrations/002_career_intelligence.sql.
- Existing main.py/config.py/database.py: no implicit production DDL, feature gate, safe diagnostic handling.
- New services/document_generation.py plus llm_client.py enhancements.
- Existing frontend types/presenters/api, ProfileEditor and page integrations; new CareerIntelligence and CareerDocuments components.
- Unit/integration/browser tests and final execution report.

## Migration and approval boundary
Test additive migration on a schema-only Neon development branch to avoid copying candidate records. Never apply the proposal to production without explicit approval and a verified backup/restore checkpoint. Production functionality requiring new tables remains disabled until that step.
A source Git baseline is not a database backup. Stage 2 testing cannot establish production readiness for an unapplied migration.

## Evidence and limitations policy
Uploaded/job text is untrusted data. The server computes evidence status; model assertions alone never grant verification. Exact/accepted aliases receive credit; related skills receive no equivalence credit. Missing candidate evidence is never excluded from a required category's denominator. Scores are compatibility estimates, not hiring probabilities.
ATS checks report extracted-text signals and explicitly disclose unavailable original PDF layout data. Safe initial tailoring is extractive/reordering; it does not invent qualifications or promise employer ATS acceptance.
