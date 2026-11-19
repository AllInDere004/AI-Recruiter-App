"""Additive Phase 2 storage; registering metadata never applies production DDL."""
from sqlalchemy import (
    JSON, Boolean, CheckConstraint, Column, DateTime, ForeignKey,
    ForeignKeyConstraint, Index, Integer, String, Text, UniqueConstraint, func,
)

from app.database import Base


class ResumeVersion(Base):
    __tablename__ = "resume_versions"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    profile_id = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"))
    parent_id = Column(Integer)
    revision = Column(Integer, nullable=False)
    fingerprint = Column(String(64), nullable=False)
    data_json = Column(JSON, nullable=False)
    source_text = Column(Text, nullable=False)
    source_metadata_json = Column(JSON, nullable=False, default=dict)
    approved = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    __table_args__ = (
        UniqueConstraint("id", "user_id", name="uq_resume_versions_owner"),
        UniqueConstraint("user_id", "revision", name="uq_resume_versions_revision"),
        CheckConstraint("revision > 0", name="ck_resume_versions_revision"),
        ForeignKeyConstraint(["parent_id", "user_id"], ["resume_versions.id", "resume_versions.user_id"], ondelete="CASCADE", name="fk_resume_versions_parent_owner"),
        Index("ix_resume_versions_history", "user_id", "created_at", "id"),
    )


class CareerReport(Base):
    __tablename__ = "career_reports"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    resume_version_id = Column(Integer, nullable=False)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"))
    kind = Column(String(20), nullable=False)
    algorithm_version = Column(String(100), nullable=False)
    profile_version = Column(String(64), nullable=False)
    job_version = Column(String(64), nullable=False)
    input_hash = Column(String(64), nullable=False)
    result_json = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    __table_args__ = (
        ForeignKeyConstraint(["resume_version_id", "user_id"], ["resume_versions.id", "resume_versions.user_id"], ondelete="CASCADE", name="fk_career_reports_resume_owner"),
        UniqueConstraint("user_id", "kind", "algorithm_version", "input_hash", name="uq_career_reports_inputs"),
        CheckConstraint("kind IN ('match', 'gap', 'ats')", name="ck_career_reports_kind"),
        Index("ix_career_reports_history", "user_id", "created_at", "id"),
        Index("ix_career_reports_job", "user_id", "job_id"),
    )


class GenerationVersion(Base):
    __tablename__ = "generation_versions"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    resume_version_id = Column(Integer, nullable=False)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    draft_id = Column(Integer, ForeignKey("drafts.id", ondelete="SET NULL"))
    lineage_id = Column(String(36), nullable=False)
    revision = Column(Integer, nullable=False)
    parent_id = Column(Integer)
    kind = Column(String(30), nullable=False)
    content_json = Column(JSON, nullable=False)
    warnings_json = Column(JSON, nullable=False, default=list)
    approved = Column(Boolean, nullable=False, default=False)
    model = Column(String(200), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    __table_args__ = (
        UniqueConstraint("id", "user_id", name="uq_generation_versions_owner"),
        UniqueConstraint("user_id", "lineage_id", "revision", name="uq_generation_versions_revision"),
        UniqueConstraint("parent_id", name="uq_generation_versions_child"),
        ForeignKeyConstraint(["parent_id", "user_id"], ["generation_versions.id", "generation_versions.user_id"], ondelete="CASCADE", name="fk_generation_versions_parent_owner"),
        ForeignKeyConstraint(["resume_version_id", "user_id"], ["resume_versions.id", "resume_versions.user_id"], ondelete="CASCADE", name="fk_generation_versions_resume_owner"),
        CheckConstraint("revision > 0", name="ck_generation_versions_revision"),
        CheckConstraint("kind IN ('tailored_resume', 'cover_letter', 'email')", name="ck_generation_versions_kind"),
        Index("ix_generation_versions_history", "user_id", "created_at", "id"),
        Index("ix_generation_versions_job", "user_id", "job_id"),
    )
