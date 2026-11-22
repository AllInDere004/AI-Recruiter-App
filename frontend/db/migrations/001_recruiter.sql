CREATE TABLE recruiter_users (
  id uuid PRIMARY KEY,
  name text NOT NULL,
  email text NOT NULL UNIQUE,
  password_hash text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE recruiter_sessions (
  token_hash text PRIMARY KEY,
  user_id uuid NOT NULL REFERENCES recruiter_users(id) ON DELETE CASCADE,
  expires_at timestamptz NOT NULL
);
CREATE INDEX recruiter_sessions_user_id_idx ON recruiter_sessions(user_id);
CREATE TABLE recruiter_profiles (
  user_id uuid PRIMARY KEY REFERENCES recruiter_users(id) ON DELETE CASCADE,
  data_json jsonb NOT NULL,
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE recruiter_jobs (
  id text PRIMARY KEY,
  user_id uuid NOT NULL REFERENCES recruiter_users(id) ON DELETE CASCADE,
  data_json jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX recruiter_jobs_owner_idx ON recruiter_jobs(user_id, created_at DESC);
CREATE TABLE recruiter_drafts (
  id text PRIMARY KEY,
  user_id uuid NOT NULL REFERENCES recruiter_users(id) ON DELETE CASCADE,
  job_id text NOT NULL REFERENCES recruiter_jobs(id) ON DELETE CASCADE,
  data_json jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX recruiter_drafts_owner_idx ON recruiter_drafts(user_id, updated_at DESC);
