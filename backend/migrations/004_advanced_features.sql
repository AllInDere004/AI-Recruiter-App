-- Phase 4: advanced features and production readiness.
-- Additive only. Requires 002_career_intelligence.sql and 003_smart_job_discovery.sql.
-- Apply with a direct (non-pooled) connection after isolated-branch verification.

BEGIN;

CREATE TABLE interview_sessions (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    job_id INTEGER REFERENCES jobs(id) ON DELETE SET NULL,
    resume_version_id BIGINT NOT NULL,
    interview_type VARCHAR(30) NOT NULL,
    difficulty VARCHAR(30) NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'in_progress',
    question_count INTEGER NOT NULL,
    time_limit_minutes INTEGER,
    prompt_version VARCHAR(100) NOT NULL,
    rubric_version VARCHAR(100) NOT NULL,
    model VARCHAR(200) NOT NULL,
    context_hash VARCHAR(64) NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(), paused_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ, evaluated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_interview_sessions_owner UNIQUE (id, user_id),
    CONSTRAINT ck_interview_sessions_type CHECK (interview_type IN ('technical','hr','behavioral','project')),
    CONSTRAINT ck_interview_sessions_difficulty CHECK (difficulty IN ('beginner','intermediate','advanced')),
    CONSTRAINT ck_interview_sessions_status CHECK (status IN ('in_progress','paused','completed','evaluated')),
    CONSTRAINT ck_interview_sessions_counts CHECK (question_count BETWEEN 1 AND 20 AND version > 0),
    CONSTRAINT ck_interview_sessions_time_limit CHECK (time_limit_minutes IS NULL OR time_limit_minutes BETWEEN 5 AND 180),
    CONSTRAINT fk_interview_sessions_resume_owner FOREIGN KEY (resume_version_id, user_id)
        REFERENCES resume_versions(id, user_id) ON DELETE CASCADE
);
CREATE INDEX ix_interview_sessions_history ON interview_sessions(user_id, created_at, id);
CREATE INDEX ix_interview_sessions_status ON interview_sessions(user_id, status, updated_at);

CREATE TABLE interview_questions (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_id BIGINT NOT NULL,
    position INTEGER NOT NULL,
    question_type VARCHAR(30) NOT NULL,
    question_text TEXT NOT NULL,
    competency VARCHAR(200) NOT NULL,
    rubric_json JSONB NOT NULL,
    follow_up_to_id BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_interview_questions_owner UNIQUE (id, user_id),
    CONSTRAINT uq_interview_questions_position UNIQUE (session_id, position),
    CONSTRAINT ck_interview_questions_position CHECK (position > 0),
    CONSTRAINT fk_interview_questions_session_owner FOREIGN KEY (session_id, user_id)
        REFERENCES interview_sessions(id, user_id) ON DELETE CASCADE,
    CONSTRAINT fk_interview_questions_followup_owner FOREIGN KEY (follow_up_to_id, user_id)
        REFERENCES interview_questions(id, user_id)
);
CREATE INDEX ix_interview_questions_session ON interview_questions(user_id, session_id, position);

CREATE TABLE interview_answers (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_id BIGINT NOT NULL,
    question_id BIGINT NOT NULL,
    answer_text TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_interview_answers_owner UNIQUE (id, user_id),
    CONSTRAINT uq_interview_answers_question UNIQUE (session_id, question_id),
    CONSTRAINT ck_interview_answers_version CHECK (version > 0),
    CONSTRAINT fk_interview_answers_session_owner FOREIGN KEY (session_id, user_id)
        REFERENCES interview_sessions(id, user_id) ON DELETE CASCADE,
    CONSTRAINT fk_interview_answers_question_owner FOREIGN KEY (question_id, user_id)
        REFERENCES interview_questions(id, user_id) ON DELETE CASCADE
);
CREATE INDEX ix_interview_answers_session ON interview_answers(user_id, session_id, question_id);

CREATE TABLE interview_evaluations (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_id BIGINT NOT NULL, question_id BIGINT NOT NULL, answer_id BIGINT NOT NULL,
    rubric_version VARCHAR(100) NOT NULL, prompt_version VARCHAR(100) NOT NULL, model VARCHAR(200) NOT NULL,
    scores_json JSONB NOT NULL, evidence_json JSONB NOT NULL, strengths_json JSONB NOT NULL,
    improvements_json JSONB NOT NULL, sample_answer TEXT NOT NULL,
    practice_score INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_interview_evaluations_owner UNIQUE (id, user_id),
    CONSTRAINT uq_interview_evaluations_answer_rubric UNIQUE (answer_id, rubric_version),
    CONSTRAINT ck_interview_evaluations_score CHECK (practice_score BETWEEN 0 AND 100),
    CONSTRAINT fk_interview_evaluations_session_owner FOREIGN KEY (session_id, user_id)
        REFERENCES interview_sessions(id, user_id) ON DELETE CASCADE,
    CONSTRAINT fk_interview_evaluations_question_owner FOREIGN KEY (question_id, user_id)
        REFERENCES interview_questions(id, user_id) ON DELETE CASCADE,
    CONSTRAINT fk_interview_evaluations_answer_owner FOREIGN KEY (answer_id, user_id)
        REFERENCES interview_answers(id, user_id) ON DELETE CASCADE
);
CREATE INDEX ix_interview_evaluations_history ON interview_evaluations(user_id, session_id, created_at);

CREATE TABLE notification_preferences (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    categories_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    email_enabled BOOLEAN NOT NULL DEFAULT false,
    timezone VARCHAR(100) NOT NULL DEFAULT 'Asia/Calcutta',
    quiet_hours_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    version INTEGER NOT NULL DEFAULT 1,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_notification_preferences_version CHECK (version > 0)
);

CREATE TABLE gmail_connections (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    google_subject VARCHAR(255) NOT NULL,
    email_hint VARCHAR(320),
    encrypted_refresh_token TEXT NOT NULL,
    scopes_json JSONB NOT NULL,
    token_expires_at TIMESTAMPTZ, revoked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE oauth_flows (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider VARCHAR(30) NOT NULL,
    state_hash VARCHAR(64) NOT NULL UNIQUE,
    code_verifier VARCHAR(200) NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL, consumed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_oauth_flows_provider CHECK (provider IN ('gmail'))
);
CREATE INDEX ix_oauth_flows_expiry ON oauth_flows(provider, expires_at);

CREATE TABLE email_send_records (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    generation_version_id BIGINT,
    recipient_hash VARCHAR(64) NOT NULL, subject_hash VARCHAR(64) NOT NULL,
    provider_message_id VARCHAR(255),
    status VARCHAR(30) NOT NULL,
    approved_at TIMESTAMPTZ NOT NULL, sent_at TIMESTAMPTZ, error_category VARCHAR(100),
    idempotency_key VARCHAR(100) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_email_send_records_status CHECK (status IN ('approved','sent','failed','cancelled')),
    CONSTRAINT fk_email_send_generation_owner FOREIGN KEY (generation_version_id, user_id)
        REFERENCES generation_versions(id, user_id)
);
CREATE INDEX ix_email_send_records_owner ON email_send_records(user_id, created_at, id);

CREATE TABLE user_roles (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role VARCHAR(30) NOT NULL,
    granted_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    granted_at TIMESTAMPTZ NOT NULL DEFAULT now(), revoked_at TIMESTAMPTZ,
    CONSTRAINT uq_user_roles_assignment UNIQUE (user_id, role),
    CONSTRAINT ck_user_roles_role CHECK (role IN ('admin'))
);
CREATE INDEX ix_user_roles_active ON user_roles(user_id, role, revoked_at);

CREATE TABLE admin_audit_events (
    id BIGSERIAL PRIMARY KEY,
    actor_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,
    target_type VARCHAR(100), target_id VARCHAR(100),
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    request_id VARCHAR(100), occurred_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_admin_audit_timeline ON admin_audit_events(occurred_at, id);

COMMIT;
