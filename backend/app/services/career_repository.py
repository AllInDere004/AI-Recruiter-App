"""Owner-scoped storage helpers. Never create or migrate schemas here."""
import hashlib
import json

from fastapi import HTTPException
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.config import settings
from app.models.intelligence import CareerReport, GenerationVersion, ResumeVersion
from app.models.profile import Profile


NEW_MODELS = (ResumeVersion, CareerReport, GenerationVersion)


def fingerprint(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def schema_ready(db) -> bool:
    """Read-only readiness check; partial deployments are never auto-repaired."""
    try:
        inspector = inspect(db.connection())
        tables = set(inspector.get_table_names())
        for model in NEW_MODELS:
            if model.__tablename__ not in tables:
                return False
            actual = {column["name"] for column in inspector.get_columns(model.__tablename__)}
            if not set(model.__table__.columns.keys()).issubset(actual):
                return False
        return True
    except SQLAlchemyError:
        db.rollback()
        return False


def require_ready(db):
    if not settings.ENABLE_CAREER_INTELLIGENCE or not schema_ready(db):
        raise HTTPException(503, "Career intelligence is currently unavailable. Your existing workspace is still available.")


def commit(db):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "This record changed concurrently. Refresh and retry.") from None
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(503, "Career data could not be saved. Please retry.") from None


def source_version(db, version: ResumeVersion) -> ResumeVersion:
    """Resolve an immutable original source through owner-scoped references."""
    current = version
    visited = set()
    while not current.source_text:
        if current.id in visited:
            raise HTTPException(409, "The resume source history needs review.")
        visited.add(current.id)
        parent_id = (current.source_metadata_json or {}).get("source_version_id") or current.parent_id
        if not parent_id:
            raise HTTPException(409, "The original resume source is unavailable.")
        current = owned(db, ResumeVersion, version.user_id, parent_id)
    return current


def resume_source(db, version: ResumeVersion) -> str:
    return source_version(db, version).source_text


def snapshot_profile(db, user_id: int, *, approved: bool, metadata=None) -> ResumeVersion:
    profile = db.query(Profile).filter(Profile.user_id == user_id).first()
    if profile is None:
        raise HTTPException(404, "Profile not found. Upload a resume first.")
    if not profile.raw_resume_text.strip() or not isinstance(profile.parsed_data, dict):
        raise HTTPException(422, "Save a readable resume and structured profile first.")
    payload = dict(profile.parsed_data)
    if profile.full_name is not None:
        payload["full_name"] = profile.full_name
    latest = db.query(ResumeVersion).filter(ResumeVersion.user_id == user_id).order_by(ResumeVersion.revision.desc()).first()
    source_metadata = dict(metadata if metadata is not None else (latest.source_metadata_json or {}) if latest else {})
    source_metadata.pop("source_version_id", None)
    digest = fingerprint({"data": payload, "source": profile.raw_resume_text, "file_sha256": source_metadata.get("sha256")})
    if latest and latest.fingerprint == digest and latest.approved == approved:
        return latest
    stored_source = profile.raw_resume_text
    if latest:
        original = source_version(db, latest)
        if original.source_text == stored_source:
            # Review/edits append structured versions without duplicating raw text.
            stored_source = ""
            source_metadata["source_version_id"] = original.id
    version = ResumeVersion(
        user_id=user_id, profile_id=profile.id, parent_id=latest.id if latest else None,
        revision=(latest.revision + 1) if latest else 1, fingerprint=digest,
        data_json=payload, source_text=stored_source,
        source_metadata_json=source_metadata, approved=approved,
    )
    db.add(version)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Your resume changed concurrently. Refresh and retry.") from None
    return version


def optional_snapshot(db, user_id: int, *, approved=False, metadata=None):
    """Preserve Phase 1 when the reviewed Phase 2 schema is not deployed."""
    if settings.ENABLE_CAREER_INTELLIGENCE and schema_ready(db):
        return snapshot_profile(db, user_id, approved=approved, metadata=metadata)
    return None


def preserve_original(db, user_id: int):
    """Capture an existing Phase 1 resume before its first Phase 2 replacement."""
    if settings.ENABLE_CAREER_INTELLIGENCE and schema_ready(db):
        has_history = db.query(ResumeVersion.id).filter(ResumeVersion.user_id == user_id).first()
        profile = db.query(Profile).filter(Profile.user_id == user_id).first()
        if not has_history and profile and profile.raw_resume_text.strip() and isinstance(profile.parsed_data, dict):
            return snapshot_profile(db, user_id, approved=False)
    return None


def owned(db, model, user_id: int, record_id: int):
    value = db.query(model).filter(model.id == record_id, model.user_id == user_id).first()
    if value is None:
        raise HTTPException(404, "Record not found.")
    return value
