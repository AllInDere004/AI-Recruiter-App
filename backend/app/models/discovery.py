from sqlalchemy import (
    JSON, Boolean, CheckConstraint, Column, DateTime, ForeignKey, ForeignKeyConstraint,
    Index, Integer, String, Text, UniqueConstraint, func,
)

from app.database import Base


class ExternalJobListing(Base):
    __tablename__ = "external_job_listings"
    id = Column(Integer, primary_key=True)
    provider = Column(String(40), nullable=False)
    provider_job_id = Column(String(255), nullable=False)
    title = Column(String(500), nullable=False)
    company = Column(String(500))
    location = Column(String(500))
    job_type = Column(String(100))
    salary_text = Column(String(500))
    experience_text = Column(String(500))
    skills_json = Column(JSON, nullable=False, default=list)
    description = Column(Text, nullable=False)
    provider_url = Column(Text, nullable=False)
    application_url = Column(Text, nullable=False)
    content_fingerprint = Column(String(64), nullable=False)
    published_at = Column(DateTime(timezone=True))
    fetched_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    expires_at = Column(DateTime(timezone=True))
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    normalized_json = Column(JSON, nullable=False, default=dict)
    __table_args__ = (
        UniqueConstraint("provider", "provider_job_id", name="uq_external_jobs_provider_id"),
        Index("ix_external_jobs_freshness", "provider", "is_active", "published_at"),
        Index("ix_external_jobs_fingerprint", "content_fingerprint"),
    )


class SavedJob(Base):
    __tablename__ = "saved_jobs"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    listing_id = Column(Integer, ForeignKey("external_job_listings.id", ondelete="CASCADE"), nullable=False)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="SET NULL"))
    notes = Column(Text)
    tags_json = Column(JSON, nullable=False, default=list)
    archived_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    __table_args__ = (
        UniqueConstraint("id", "user_id", name="uq_saved_jobs_owner"),
        UniqueConstraint("user_id", "listing_id", name="uq_saved_jobs_listing"),
        Index("ix_saved_jobs_owner_state", "user_id", "archived_at", "created_at"),
    )


class JobPreference(Base):
    __tablename__ = "job_preferences"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    roles_json = Column(JSON, nullable=False, default=list)
    locations_json = Column(JSON, nullable=False, default=list)
    remote_policy = Column(String(30), nullable=False, default="any", server_default="any")
    experience_levels_json = Column(JSON, nullable=False, default=list)
    job_types_json = Column(JSON, nullable=False, default=list)
    timezone = Column(String(100), nullable=False, default="Asia/Calcutta", server_default="Asia/Calcutta")
    version = Column(Integer, nullable=False, default=1, server_default="1")
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    __table_args__ = (
        CheckConstraint("version > 0", name="ck_job_preferences_version"),
    )


class Application(Base):
    __tablename__ = "applications"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    saved_job_id = Column(Integer, nullable=False)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="SET NULL"))
    status = Column(String(30), nullable=False, default="Saved", server_default="Saved")
    submitted_at = Column(DateTime(timezone=True))
    application_date = Column(DateTime(timezone=True))
    recruiter_name = Column(String(500))
    recruiter_email = Column(String(500))
    notes = Column(Text)
    interview_at = Column(DateTime(timezone=True))
    deadline_at = Column(DateTime(timezone=True))
    resume_version_id = Column(Integer)
    email_version_id = Column(Integer)
    cover_letter_version_id = Column(Integer)
    version = Column(Integer, nullable=False, default=1, server_default="1")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    __table_args__ = (
        UniqueConstraint("id", "user_id", name="uq_applications_owner"),
        UniqueConstraint("user_id", "saved_job_id", name="uq_applications_saved_job"),
        ForeignKeyConstraint(["saved_job_id", "user_id"], ["saved_jobs.id", "saved_jobs.user_id"], ondelete="CASCADE", name="fk_applications_saved_owner"),
        ForeignKeyConstraint(["resume_version_id", "user_id"], ["resume_versions.id", "resume_versions.user_id"], name="fk_applications_resume_owner"),
        ForeignKeyConstraint(["email_version_id", "user_id"], ["generation_versions.id", "generation_versions.user_id"], name="fk_applications_email_owner"),
        ForeignKeyConstraint(["cover_letter_version_id", "user_id"], ["generation_versions.id", "generation_versions.user_id"], name="fk_applications_cover_owner"),
        CheckConstraint("status IN ('Saved','Preparing','Applied','Assessment','Interview','Offer','Rejected','Withdrawn')", name="ck_applications_status"),
        CheckConstraint("version > 0", name="ck_applications_version"),
        Index("ix_applications_owner_status", "user_id", "status", "updated_at"),
        Index("ix_applications_owner_dates", "user_id", "application_date", "interview_at", "deadline_at"),
    )


class ApplicationEvent(Base):
    __tablename__ = "application_events"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    application_id = Column(Integer)
    event_type = Column(String(50), nullable=False)
    from_status = Column(String(30))
    to_status = Column(String(30))
    context_json = Column(JSON, nullable=False, default=dict)
    occurred_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    __table_args__ = (
        ForeignKeyConstraint(["application_id", "user_id"], ["applications.id", "applications.user_id"], ondelete="CASCADE", name="fk_application_events_owner"),
        Index("ix_application_events_timeline", "user_id", "occurred_at", "id"),
        Index("ix_application_events_application", "user_id", "application_id", "occurred_at"),
    )


class Reminder(Base):
    __tablename__ = "reminders"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    application_id = Column(Integer)
    kind = Column(String(40), nullable=False)
    title = Column(String(500), nullable=False)
    note = Column(Text)
    due_at = Column(DateTime(timezone=True), nullable=False)
    timezone = Column(String(100), nullable=False)
    state = Column(String(30), nullable=False, default="upcoming", server_default="upcoming")
    snoozed_until = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    dismissed_at = Column(DateTime(timezone=True))
    delivery_key = Column(String(100), nullable=False, unique=True)
    lease_token = Column(String(100))
    lease_until = Column(DateTime(timezone=True))
    attempts = Column(Integer, nullable=False, default=0, server_default="0")
    version = Column(Integer, nullable=False, default=1, server_default="1")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    __table_args__ = (
        UniqueConstraint("id", "user_id", name="uq_reminders_owner"),
        ForeignKeyConstraint(["application_id", "user_id"], ["applications.id", "applications.user_id"], ondelete="CASCADE", name="fk_reminders_application_owner"),
        CheckConstraint("state IN ('upcoming','overdue','completed','snoozed','dismissed')", name="ck_reminders_state"),
        CheckConstraint("attempts >= 0 AND version > 0", name="ck_reminders_counters"),
        Index("ix_reminders_due_claim", "state", "due_at", "lease_until"),
        Index("ix_reminders_owner_state", "user_id", "state", "due_at"),
    )


class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    reminder_id = Column(Integer)
    notification_type = Column(String(40), nullable=False, default="reminder", server_default="reminder")
    title = Column(String(500), nullable=False)
    message = Column(Text, nullable=False)
    delivery_key = Column(String(120), nullable=False, unique=True)
    read_at = Column(DateTime(timezone=True))
    dismissed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    __table_args__ = (
        ForeignKeyConstraint(["reminder_id", "user_id"], ["reminders.id", "reminders.user_id"], ondelete="CASCADE", name="fk_notifications_reminder_owner"),
        Index("ix_notifications_owner_unread", "user_id", "read_at", "dismissed_at", "created_at"),
    )


class RecommendationCache(Base):
    __tablename__ = "recommendation_cache"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    listing_id = Column(Integer, ForeignKey("external_job_listings.id", ondelete="CASCADE"), nullable=False)
    resume_version_id = Column(Integer)
    algorithm_version = Column(String(100), nullable=False)
    input_hash = Column(String(64), nullable=False)
    result_json = Column(JSON, nullable=False)
    listing_fetched_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(["resume_version_id", "user_id"], ["resume_versions.id", "resume_versions.user_id"], ondelete="CASCADE", name="fk_recommendation_resume_owner"),
        UniqueConstraint("user_id", "listing_id", "algorithm_version", "input_hash", name="uq_recommendation_inputs"),
        Index("ix_recommendation_owner_expiry", "user_id", "expires_at"),
    )
