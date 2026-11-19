"""Additive Phase 4 persistence. Importing metadata never applies production DDL."""
from sqlalchemy import (
    JSON, Boolean, CheckConstraint, Column, DateTime, ForeignKey, ForeignKeyConstraint,
    Index, Integer, String, Text, UniqueConstraint, func,
)

from app.database import Base


class InterviewSession(Base):
    __tablename__ = "interview_sessions"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="SET NULL"))
    resume_version_id = Column(Integer, nullable=False)
    interview_type = Column(String(30), nullable=False)
    difficulty = Column(String(30), nullable=False)
    status = Column(String(30), nullable=False, default="in_progress", server_default="in_progress")
    question_count = Column(Integer, nullable=False)
    time_limit_minutes = Column(Integer)
    prompt_version = Column(String(100), nullable=False)
    rubric_version = Column(String(100), nullable=False)
    model = Column(String(200), nullable=False)
    context_hash = Column(String(64), nullable=False)
    version = Column(Integer, nullable=False, default=1, server_default="1")
    started_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    paused_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    evaluated_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    __table_args__ = (
        UniqueConstraint("id", "user_id", name="uq_interview_sessions_owner"),
        ForeignKeyConstraint(["resume_version_id", "user_id"], ["resume_versions.id", "resume_versions.user_id"], ondelete="CASCADE", name="fk_interview_sessions_resume_owner"),
        CheckConstraint("interview_type IN ('technical','hr','behavioral','project')", name="ck_interview_sessions_type"),
        CheckConstraint("difficulty IN ('beginner','intermediate','advanced')", name="ck_interview_sessions_difficulty"),
        CheckConstraint("status IN ('in_progress','paused','completed','evaluated')", name="ck_interview_sessions_status"),
        CheckConstraint("question_count BETWEEN 1 AND 20 AND version > 0", name="ck_interview_sessions_counts"),
        Index("ix_interview_sessions_history", "user_id", "created_at", "id"),
        Index("ix_interview_sessions_status", "user_id", "status", "updated_at"),
    )


class InterviewQuestion(Base):
    __tablename__ = "interview_questions"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    session_id = Column(Integer, nullable=False)
    position = Column(Integer, nullable=False)
    question_type = Column(String(30), nullable=False)
    question_text = Column(Text, nullable=False)
    competency = Column(String(200), nullable=False)
    rubric_json = Column(JSON, nullable=False)
    follow_up_to_id = Column(Integer)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    __table_args__ = (
        UniqueConstraint("id", "user_id", name="uq_interview_questions_owner"),
        UniqueConstraint("session_id", "position", name="uq_interview_questions_position"),
        ForeignKeyConstraint(["session_id", "user_id"], ["interview_sessions.id", "interview_sessions.user_id"], ondelete="CASCADE", name="fk_interview_questions_session_owner"),
        ForeignKeyConstraint(["follow_up_to_id", "user_id"], ["interview_questions.id", "interview_questions.user_id"], name="fk_interview_questions_followup_owner"),
        CheckConstraint("position > 0", name="ck_interview_questions_position"),
        Index("ix_interview_questions_session", "user_id", "session_id", "position"),
    )


class InterviewAnswer(Base):
    __tablename__ = "interview_answers"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    session_id = Column(Integer, nullable=False)
    question_id = Column(Integer, nullable=False)
    answer_text = Column(Text, nullable=False)
    version = Column(Integer, nullable=False, default=1, server_default="1")
    submitted_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    __table_args__ = (
        UniqueConstraint("id", "user_id", name="uq_interview_answers_owner"),
        UniqueConstraint("session_id", "question_id", name="uq_interview_answers_question"),
        ForeignKeyConstraint(["session_id", "user_id"], ["interview_sessions.id", "interview_sessions.user_id"], ondelete="CASCADE", name="fk_interview_answers_session_owner"),
        ForeignKeyConstraint(["question_id", "user_id"], ["interview_questions.id", "interview_questions.user_id"], ondelete="CASCADE", name="fk_interview_answers_question_owner"),
        CheckConstraint("version > 0", name="ck_interview_answers_version"),
        Index("ix_interview_answers_session", "user_id", "session_id", "question_id"),
    )


class InterviewEvaluation(Base):
    __tablename__ = "interview_evaluations"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    session_id = Column(Integer, nullable=False)
    question_id = Column(Integer, nullable=False)
    answer_id = Column(Integer, nullable=False)
    rubric_version = Column(String(100), nullable=False)
    prompt_version = Column(String(100), nullable=False)
    model = Column(String(200), nullable=False)
    scores_json = Column(JSON, nullable=False)
    evidence_json = Column(JSON, nullable=False)
    strengths_json = Column(JSON, nullable=False)
    improvements_json = Column(JSON, nullable=False)
    sample_answer = Column(Text, nullable=False)
    practice_score = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    __table_args__ = (
        UniqueConstraint("id", "user_id", name="uq_interview_evaluations_owner"),
        UniqueConstraint("answer_id", "rubric_version", name="uq_interview_evaluations_answer_rubric"),
        ForeignKeyConstraint(["session_id", "user_id"], ["interview_sessions.id", "interview_sessions.user_id"], ondelete="CASCADE", name="fk_interview_evaluations_session_owner"),
        ForeignKeyConstraint(["question_id", "user_id"], ["interview_questions.id", "interview_questions.user_id"], ondelete="CASCADE", name="fk_interview_evaluations_question_owner"),
        ForeignKeyConstraint(["answer_id", "user_id"], ["interview_answers.id", "interview_answers.user_id"], ondelete="CASCADE", name="fk_interview_evaluations_answer_owner"),
        CheckConstraint("practice_score BETWEEN 0 AND 100", name="ck_interview_evaluations_score"),
        Index("ix_interview_evaluations_history", "user_id", "session_id", "created_at"),
    )


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    categories_json = Column(JSON, nullable=False, default=dict)
    email_enabled = Column(Boolean, nullable=False, default=False, server_default="false")
    timezone = Column(String(100), nullable=False, default="Asia/Calcutta", server_default="Asia/Calcutta")
    quiet_hours_json = Column(JSON, nullable=False, default=dict)
    version = Column(Integer, nullable=False, default=1, server_default="1")
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    __table_args__ = (CheckConstraint("version > 0", name="ck_notification_preferences_version"),)


class GmailConnection(Base):
    __tablename__ = "gmail_connections"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    google_subject = Column(String(255), nullable=False)
    email_hint = Column(String(320))
    encrypted_refresh_token = Column(Text, nullable=False)
    scopes_json = Column(JSON, nullable=False)
    token_expires_at = Column(DateTime(timezone=True))
    revoked_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class OAuthFlow(Base):
    __tablename__ = "oauth_flows"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    provider = Column(String(30), nullable=False)
    state_hash = Column(String(64), nullable=False, unique=True)
    code_verifier = Column(String(200), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    consumed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    __table_args__ = (
        CheckConstraint("provider IN ('gmail')", name="ck_oauth_flows_provider"),
        Index("ix_oauth_flows_expiry", "provider", "expires_at"),
    )


class EmailSendRecord(Base):
    __tablename__ = "email_send_records"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    generation_version_id = Column(Integer)
    recipient_hash = Column(String(64), nullable=False)
    subject_hash = Column(String(64), nullable=False)
    provider_message_id = Column(String(255))
    status = Column(String(30), nullable=False)
    approved_at = Column(DateTime(timezone=True), nullable=False)
    sent_at = Column(DateTime(timezone=True))
    error_category = Column(String(100))
    idempotency_key = Column(String(100), nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    __table_args__ = (
        ForeignKeyConstraint(["generation_version_id", "user_id"], ["generation_versions.id", "generation_versions.user_id"], name="fk_email_send_generation_owner"),
        CheckConstraint("status IN ('approved','sent','failed','cancelled')", name="ck_email_send_records_status"),
        Index("ix_email_send_records_owner", "user_id", "created_at", "id"),
    )


class UserRole(Base):
    __tablename__ = "user_roles"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(30), nullable=False)
    granted_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    granted_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    revoked_at = Column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("user_id", "role", name="uq_user_roles_assignment"),
        CheckConstraint("role IN ('admin')", name="ck_user_roles_role"),
        Index("ix_user_roles_active", "user_id", "role", "revoked_at"),
    )


class AdminAuditEvent(Base):
    __tablename__ = "admin_audit_events"
    id = Column(Integer, primary_key=True)
    actor_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    action = Column(String(100), nullable=False)
    target_type = Column(String(100))
    target_id = Column(String(100))
    metadata_json = Column(JSON, nullable=False, default=dict)
    request_id = Column(String(100))
    occurred_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    __table_args__ = (Index("ix_admin_audit_timeline", "occurred_at", "id"),)
