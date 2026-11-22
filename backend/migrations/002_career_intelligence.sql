-- REVIEWED PROPOSAL ONLY. Never invoked by application startup.
-- Apply to a Neon development branch first. Production requires explicit approval
-- and a verified backup. All ten pre-existing tables and their rows are preserved.
BEGIN;

CREATE TABLE resume_versions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    profile_id INTEGER REFERENCES profiles(id) ON DELETE SET NULL,
    parent_id INTEGER,
    revision INTEGER NOT NULL,
    fingerprint VARCHAR(64) NOT NULL,
    data_json JSONB NOT NULL,
    source_text TEXT NOT NULL,
    source_metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    approved BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_resume_versions_owner UNIQUE (id, user_id),
    CONSTRAINT uq_resume_versions_revision UNIQUE (user_id, revision),
    CONSTRAINT ck_resume_versions_revision CHECK (revision > 0),
    CONSTRAINT fk_resume_versions_parent_owner FOREIGN KEY (parent_id, user_id)
        REFERENCES resume_versions(id, user_id) ON DELETE CASCADE
);
CREATE INDEX ix_resume_versions_history ON resume_versions(user_id, created_at, id);

CREATE TABLE career_reports (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    resume_version_id INTEGER NOT NULL,
    job_id INTEGER REFERENCES jobs(id) ON DELETE CASCADE,
    kind VARCHAR(20) NOT NULL,
    algorithm_version VARCHAR(100) NOT NULL,
    profile_version VARCHAR(64) NOT NULL,
    job_version VARCHAR(64) NOT NULL,
    input_hash VARCHAR(64) NOT NULL,
    result_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_career_reports_resume_owner FOREIGN KEY (resume_version_id, user_id)
        REFERENCES resume_versions(id, user_id) ON DELETE CASCADE,
    CONSTRAINT uq_career_reports_inputs UNIQUE (user_id, kind, algorithm_version, input_hash),
    CONSTRAINT ck_career_reports_kind CHECK (kind IN ('match', 'gap', 'ats'))
);
CREATE INDEX ix_career_reports_history ON career_reports(user_id, created_at, id);
CREATE INDEX ix_career_reports_job ON career_reports(user_id, job_id);

CREATE TABLE generation_versions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    resume_version_id INTEGER NOT NULL,
    job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    draft_id INTEGER REFERENCES drafts(id) ON DELETE SET NULL,
    lineage_id VARCHAR(36) NOT NULL,
    revision INTEGER NOT NULL,
    parent_id INTEGER,
    kind VARCHAR(30) NOT NULL,
    content_json JSONB NOT NULL,
    warnings_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    approved BOOLEAN NOT NULL DEFAULT FALSE,
    model VARCHAR(200) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_generation_versions_owner UNIQUE (id, user_id),
    CONSTRAINT uq_generation_versions_revision UNIQUE (user_id, lineage_id, revision),
    CONSTRAINT uq_generation_versions_child UNIQUE (parent_id),
    CONSTRAINT fk_generation_versions_parent_owner FOREIGN KEY (parent_id, user_id)
        REFERENCES generation_versions(id, user_id) ON DELETE CASCADE,
    CONSTRAINT fk_generation_versions_resume_owner FOREIGN KEY (resume_version_id, user_id)
        REFERENCES resume_versions(id, user_id) ON DELETE CASCADE,
    CONSTRAINT ck_generation_versions_revision CHECK (revision > 0),
    CONSTRAINT ck_generation_versions_kind CHECK (kind IN ('tailored_resume', 'cover_letter', 'email'))
);
CREATE INDEX ix_generation_versions_history ON generation_versions(user_id, created_at, id);
CREATE INDEX ix_generation_versions_job ON generation_versions(user_id, job_id);

COMMIT;
