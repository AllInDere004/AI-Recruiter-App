-- REVIEWED PROPOSAL ONLY. Never invoked by application startup.
-- Apply after 002_career_intelligence.sql on a Neon development branch first.
-- Production requires a verified backup/restore checkpoint and explicit approval.
BEGIN;

CREATE TABLE external_job_listings (
    id SERIAL PRIMARY KEY,
    provider VARCHAR(40) NOT NULL,
    provider_job_id VARCHAR(255) NOT NULL,
    title VARCHAR(500) NOT NULL,
    company VARCHAR(500),
    location VARCHAR(500),
    job_type VARCHAR(100),
    salary_text VARCHAR(500),
    experience_text VARCHAR(500),
    skills_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    description TEXT NOT NULL,
    provider_url TEXT NOT NULL,
    application_url TEXT NOT NULL,
    content_fingerprint VARCHAR(64) NOT NULL,
    published_at TIMESTAMPTZ,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    normalized_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT uq_external_jobs_provider_id UNIQUE (provider, provider_job_id)
);
CREATE INDEX ix_external_jobs_freshness ON external_job_listings(provider, is_active, published_at);
CREATE INDEX ix_external_jobs_fingerprint ON external_job_listings(content_fingerprint);

CREATE TABLE saved_jobs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    listing_id INTEGER NOT NULL REFERENCES external_job_listings(id) ON DELETE CASCADE,
    job_id INTEGER REFERENCES jobs(id) ON DELETE SET NULL,
    notes TEXT,
    tags_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    archived_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ,
    CONSTRAINT uq_saved_jobs_owner UNIQUE (id, user_id),
    CONSTRAINT uq_saved_jobs_listing UNIQUE (user_id, listing_id)
);
CREATE INDEX ix_saved_jobs_owner_state ON saved_jobs(user_id, archived_at, created_at);

CREATE TABLE job_preferences (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    roles_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    locations_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    remote_policy VARCHAR(30) NOT NULL DEFAULT 'any',
    experience_levels_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    job_types_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    timezone VARCHAR(100) NOT NULL DEFAULT 'Asia/Calcutta',
    version INTEGER NOT NULL DEFAULT 1,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_job_preferences_version CHECK (version > 0)
);

CREATE TABLE applications (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    saved_job_id INTEGER NOT NULL,
    job_id INTEGER REFERENCES jobs(id) ON DELETE SET NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'Saved',
    submitted_at TIMESTAMPTZ,
    application_date TIMESTAMPTZ,
    recruiter_name VARCHAR(500),
    recruiter_email VARCHAR(500),
    notes TEXT,
    interview_at TIMESTAMPTZ,
    deadline_at TIMESTAMPTZ,
    resume_version_id INTEGER,
    email_version_id INTEGER,
    cover_letter_version_id INTEGER,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_applications_owner UNIQUE (id, user_id),
    CONSTRAINT uq_applications_saved_job UNIQUE (user_id, saved_job_id),
    CONSTRAINT fk_applications_saved_owner FOREIGN KEY (saved_job_id, user_id)
        REFERENCES saved_jobs(id, user_id) ON DELETE CASCADE,
    CONSTRAINT fk_applications_resume_owner FOREIGN KEY (resume_version_id, user_id)
        REFERENCES resume_versions(id, user_id),
    CONSTRAINT fk_applications_email_owner FOREIGN KEY (email_version_id, user_id)
        REFERENCES generation_versions(id, user_id),
    CONSTRAINT fk_applications_cover_owner FOREIGN KEY (cover_letter_version_id, user_id)
        REFERENCES generation_versions(id, user_id),
    CONSTRAINT ck_applications_status CHECK (status IN ('Saved','Preparing','Applied','Assessment','Interview','Offer','Rejected','Withdrawn')),
    CONSTRAINT ck_applications_version CHECK (version > 0)
);
CREATE INDEX ix_applications_owner_status ON applications(user_id, status, updated_at);
CREATE INDEX ix_applications_owner_dates ON applications(user_id, application_date, interview_at, deadline_at);

CREATE TABLE application_events (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    application_id INTEGER,
    event_type VARCHAR(50) NOT NULL,
    from_status VARCHAR(30),
    to_status VARCHAR(30),
    context_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_application_events_owner FOREIGN KEY (application_id, user_id)
        REFERENCES applications(id, user_id) ON DELETE CASCADE
);
CREATE INDEX ix_application_events_timeline ON application_events(user_id, occurred_at, id);
CREATE INDEX ix_application_events_application ON application_events(user_id, application_id, occurred_at);

CREATE TABLE reminders (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    application_id INTEGER,
    kind VARCHAR(40) NOT NULL,
    title VARCHAR(500) NOT NULL,
    note TEXT,
    due_at TIMESTAMPTZ NOT NULL,
    timezone VARCHAR(100) NOT NULL,
    state VARCHAR(30) NOT NULL DEFAULT 'upcoming',
    snoozed_until TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    dismissed_at TIMESTAMPTZ,
    delivery_key VARCHAR(100) NOT NULL UNIQUE,
    lease_token VARCHAR(100),
    lease_until TIMESTAMPTZ,
    attempts INTEGER NOT NULL DEFAULT 0,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_reminders_owner UNIQUE (id, user_id),
    CONSTRAINT fk_reminders_application_owner FOREIGN KEY (application_id, user_id)
        REFERENCES applications(id, user_id) ON DELETE CASCADE,
    CONSTRAINT ck_reminders_state CHECK (state IN ('upcoming','overdue','completed','snoozed','dismissed')),
    CONSTRAINT ck_reminders_counters CHECK (attempts >= 0 AND version > 0)
);
CREATE INDEX ix_reminders_due_claim ON reminders(state, due_at, lease_until);
CREATE INDEX ix_reminders_owner_state ON reminders(user_id, state, due_at);

CREATE TABLE notifications (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    reminder_id INTEGER,
    notification_type VARCHAR(40) NOT NULL DEFAULT 'reminder',
    title VARCHAR(500) NOT NULL,
    message TEXT NOT NULL,
    delivery_key VARCHAR(120) NOT NULL UNIQUE,
    read_at TIMESTAMPTZ,
    dismissed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_notifications_reminder_owner FOREIGN KEY (reminder_id, user_id)
        REFERENCES reminders(id, user_id) ON DELETE CASCADE
);
CREATE INDEX ix_notifications_owner_unread ON notifications(user_id, read_at, dismissed_at, created_at);

CREATE TABLE recommendation_cache (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    listing_id INTEGER NOT NULL REFERENCES external_job_listings(id) ON DELETE CASCADE,
    resume_version_id INTEGER,
    algorithm_version VARCHAR(100) NOT NULL,
    input_hash VARCHAR(64) NOT NULL,
    result_json JSONB NOT NULL,
    listing_fetched_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT fk_recommendation_resume_owner FOREIGN KEY (resume_version_id, user_id)
        REFERENCES resume_versions(id, user_id) ON DELETE CASCADE,
    CONSTRAINT uq_recommendation_inputs UNIQUE (user_id, listing_id, algorithm_version, input_hash)
);
CREATE INDEX ix_recommendation_owner_expiry ON recommendation_cache(user_id, expires_at);

COMMIT;
