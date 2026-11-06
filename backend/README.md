# FastAPI backend

Run commands from this directory:

```powershell
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8001
```

Keep your backend settings in `backend/.env`. Set `DATABASE_URL`, `JWT_SECRET_KEY`, and
`LLM_API_KEY` (your Google Gemini API key). `LLM_MODEL` defaults to
`gemini-2.5-flash` and can be changed to a model available to your account.
The backend resolves this file relative to its source directory, so it works from
any working directory. Root `.env` and `.env.local` provide fallback values;
`backend/.env` overrides them, and process environment variables take priority.
Restart the backend after changing environment settings.
Either `LLM_API_KEY` or `GEMINI_API_KEY` configures the Gemini client;
`LLM_API_KEY` takes priority when both names exist in the same settings source.
Settings are loaded once at process startup; restart Uvicorn after editing `.env`.
Never commit `.env` or send API keys in browser requests.

## Resume and profile routes

Authenticate with `POST /api/auth/login` using JSON `{ "email": "...", "password": "..." }`.
Pass the returned JWT as `Authorization: Bearer <access_token>` to:

- `POST /api/resume/upload`: multipart form field `file`, content type `application/pdf`.
- `GET /api/profile/me`: retrieve your saved profile.
- `PUT /api/profile/me`: JSON containing `full_name`, `parsed_data`, or both.

Uploads accept text-based PDFs up to 10 MB. Encrypted, malformed, empty, or scanned
PDFs without extractable text return a clear error; OCR is not performed. A successful
upload extracts text in memory, asks Gemini for JSON, validates it, then creates or
updates the signed-in user's profile. Failed parsing or Gemini calls do not overwrite
saved data. Re-uploading updates the same profile record.

Manual edits preserve omitted fields. Explicit null clears an optional field.
`parsed_data`, when supplied, replaces the saved dictionary. Profile reads and edits
return 404 until the user has uploaded a resume. A missing Gemini API key returns 503;
provider or invalid-response errors return 502.

## Tests

```powershell
python -m pip install -r requirements-dev.txt
python -B -m unittest discover -s tests -v
```

Tests use isolated in-memory databases and real generated PDFs. Gemini is mocked at
the SDK boundary; no live API key or production database writes are needed.

## Job analysis and matching

- `POST /api/jobs/analyze`: JSON with `description` and optional `title`/`company`.
  Gemini extracts required skills and responsibilities; explicit title/company values
  take priority over extracted values. The response and saved `extracted_skills`
  dictionary include the analyzed title, company, required skills, and responsibilities.
- `GET /api/jobs/`: list only the signed-in user's saved jobs, newest first.
- `POST /api/match/compare`: JSON `{ "job_id": 1 }`. Requires the user's saved resume
  and an owned job. Returns `overall_score`, `matched_skills`, `missing_skills`, and
  an explanatory summary.

Matching uses `sentence-transformers/all-MiniLM-L6-v2`, loaded lazily on the first
comparison. The first request may download model weights into the Hugging Face cache;
subsequent comparisons reuse the model. An unavailable model returns 503, without
substituting a fake score. Network access is needed if the weights are not cached.
MiniLM truncates inputs to its supported token length; scores reflect that model limit.

The overall score is 0-100: 70% nonnegative cosine similarity and 30% required-skill
coverage. If no required skills are listed, semantic similarity alone determines the
score. Skill matching ignores case, whitespace, and duplicate requirements, and
preserves the displayed names from the job. It does not guess skill aliases.

Job analysis requires the Gemini key configured above. Semantic matching runs locally
and does not send resume text to Gemini. These are similarity and coverage measures,
not calibrated hiring probabilities. Routes enforce job and profile ownership.

## Email generation and draft tracker

- `POST /api/email/generate`: JSON with an owned `job_id`, `situation`, `tone`, and
  optional `custom_notes`. Supported situation templates are `apply`, `cold_email`,
  `follow_up`, `thank_you`, `referral`, and `reply_recruiter`; other values or missing
  template files use a standard prompt.
- `GET /api/drafts/`: list the signed-in user's drafts, newest first.
- `GET /api/drafts/{draft_id}`: retrieve an owned draft.
- `PUT /api/drafts/{draft_id}`: edit `subject_line`, `body`, `situation`, or `tone`.
  Omitted fields are preserved. A null subject is allowed; supplied body, situation,
  and tone must be nonempty. Changing the body clears the old `match_score`, since
  that score describes the generated body, not the manually edited text.
- `DELETE /api/drafts/{draft_id}`: remove an owned draft (204 with no response body).

Generation makes two Gemini calls: one to generate validated JSON with a subject and
body, and one to identify candidate claims unsupported by the raw resume. Warnings
are returned with the generated draft, including the subject in factual review.
Warnings identify unverified claims, not proven falsehoods, and are advisory rather
than a guarantee of factual correctness. They are returned by generation and are not
stored in the Draft table. Notes and job requirements are not proof of past candidate
achievements. Generation, verification, or scoring failures do not save a partial draft.

The 0-100 score weights semantic alignment 75% and key phrase coverage 25%.
Semantic alignment weights the job-to-email cosine similarity 60% and the
resume-to-email similarity 40%, clamping negative similarities to zero. Phrase
coverage uses job content words and two-word phrases, excluding stop words.
It is an alignment heuristic, not a hiring probability or factual verification result.
If no key phrases remain, semantic alignment alone determines the score.

The test suite covers this workflow with isolated databases, mocked Gemini responses,
and deterministic embedding vectors; the standalone real-model check verifies the
MiniLM embedding path separately.

## Next.js integration

The frontend uses `NEXT_PUBLIC_API_URL=http://localhost:8001` in
`frontend/.env.local`, and calls the FastAPI `/api/...` endpoints directly.
Bearer JWTs are stored under `ai_recruiter_token`; registration returns a user and
redirects to sign-in, while login obtains a token and fetches `/api/auth/me`.
No sample accounts, mock data, client-generated scores, or local-storage persistence
fallbacks are used. A new user uploads a resume to create a profile before editing it.

The tracker persists `Draft`, `Sent`, `Replied`, `Interview`, and `Rejected` in the
backend `drafts.status` column. Startup adds this column to older tables with a
`Draft` default and preserves existing records. Tracker edits use PUT and deletions
use DELETE; the browser joins owned jobs onto drafts for display. Generation already
saves a draft, so the review page updates that record rather than creating a duplicate.
The older Next.js `/api` implementation is not used by this frontend client.

Run the frontend with `npm run dev` from the repository root. Restart Next.js after
changing `NEXT_PUBLIC_API_URL` (rebuild when using a production server).
