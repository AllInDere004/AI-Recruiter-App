import hashlib
import json
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import inspect

from app.config import settings
from app.models.discovery import ExternalJobListing
from app.providers.base import NormalizedJob


REQUIRED_TABLES = {
    "external_job_listings", "saved_jobs", "job_preferences", "applications",
    "application_events", "reminders", "notifications", "recommendation_cache",
}


def schema_ready(db) -> bool:
    try:
        return REQUIRED_TABLES.issubset(set(inspect(db.get_bind()).get_table_names()))
    except Exception:
        return False


def require_ready(db):
    if not settings.ENABLE_JOB_DISCOVERY or not schema_ready(db):
        raise HTTPException(503, "Job discovery is currently unavailable. Your existing workspace is still available.")


def fingerprint(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def upsert_listing(db, item: NormalizedJob) -> ExternalJobListing:
    row = db.query(ExternalJobListing).filter_by(provider=item.provider, provider_job_id=item.provider_job_id).first()
    if row is None:
        row = ExternalJobListing(provider=item.provider, provider_job_id=item.provider_job_id)
        db.add(row)
    content = item.as_dict()
    row.title = item.title
    row.company = item.company
    row.location = item.location
    row.job_type = item.job_type
    row.salary_text = item.salary_text
    row.experience_text = item.experience_text
    row.skills_json = item.skills
    row.description = item.description
    row.provider_url = item.provider_url
    row.application_url = item.application_url
    row.published_at = item.published_at
    row.expires_at = item.expires_at
    row.fetched_at = datetime.now(timezone.utc)
    row.is_active = True
    row.normalized_json = item.normalized
    row.content_fingerprint = fingerprint(content)
    db.flush()
    return row
