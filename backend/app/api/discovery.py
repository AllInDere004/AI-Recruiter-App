from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.discovery import ExternalJobListing, JobPreference, SavedJob
from app.models.job import Job
from app.models.user import User
from app.providers.base import NormalizedJob, ProviderError
from app.providers.himalayas import HimalayasProvider
from app.providers.jooble import JoobleProvider
from app.schemas.discovery import ImportPreviewRequest, ImportSaveRequest, PreferenceUpdate, SaveJobRequest, SavedJobUpdate
from app.services.ai_usage import enforce_ai_usage
from app.services.auth_service import get_current_user
from app.services.discovery_repository import require_ready, schema_ready, upsert_listing
from app.services.request_limits import enforce_request_limit
from app.services.job_analyzer import analyze_job_description
from app.services.job_import import (
    ImportSecurityError, ImportUnavailableError, extract_job_text, fetch_public_page,
    preview_token, robots_allowed, validate_public_https_url, verify_preview_token,
)
from app.services.llm_client import LLMConfigurationError, LLMError
from app.services.discovery_repository import fingerprint
from app.services.recommendations import recommend


router = APIRouter(prefix="/api/discovery", tags=["Job discovery"])


def _provider():
    provider = settings.JOB_PROVIDER.casefold()
    if provider == "himalayas":
        return HimalayasProvider(api_key=settings.HIMALAYAS_API_KEY,
                                 base_url=settings.HIMALAYAS_API_BASE_URL,
                                 timeout=settings.JOB_PROVIDER_TIMEOUT_SECONDS)
    if provider == "jooble":
        return JoobleProvider(api_key=settings.JOOBLE_API_KEY, base_url=settings.JOOBLE_API_BASE_URL,
                              timeout=settings.JOB_PROVIDER_TIMEOUT_SECONDS)
    raise HTTPException(503, "The configured job provider is not supported.")


def _freshness(value):
    if value is None:
        return "unknown"
    now = datetime.now(timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    age = now - value
    return "today" if age <= timedelta(days=1) else "recent" if age <= timedelta(days=14) else "older"


def _listing(row, saved_id=None):
    return {
        "id": row.id, "provider": row.provider, "provider_job_id": row.provider_job_id,
        "title": row.title, "company": row.company, "location": row.location,
        "job_type": row.job_type, "salary_text": row.salary_text,
        "experience_text": row.experience_text, "skills": row.skills_json or [],
        "description": row.description, "provider_url": row.provider_url,
        "application_url": row.application_url, "published_at": row.published_at,
        "fetched_at": row.fetched_at, "freshness": _freshness(row.published_at or row.fetched_at),
        "saved_job_id": saved_id,
    }


def _saved(value):
    return {
        "id": value.id, "listing": _listing(value._listing, value.id), "job_id": value.job_id,
        "notes": value.notes, "tags": value.tags_json or [], "archived_at": value.archived_at,
        "created_at": value.created_at, "updated_at": value.updated_at,
    }


def _owned_saved(db, user_id, saved_id):
    value = db.query(SavedJob).filter(SavedJob.id == saved_id, SavedJob.user_id == user_id).first()
    if value is None:
        raise HTTPException(404, "Saved job not found.")
    value._listing = db.query(ExternalJobListing).filter(ExternalJobListing.id == value.listing_id).one()
    return value


def _ai_error(error):
    if isinstance(error, LLMConfigurationError):
        raise HTTPException(503, str(error)) from None
    code = getattr(error, "provider_status", None)
    raise HTTPException(429 if code == 429 else 503 if code in {408, 500, 502, 503, 504} else 502, str(error)) from None


@router.get("/status")
def status(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    provider = _provider()
    ready = bool(settings.ENABLE_JOB_DISCOVERY and schema_ready(db))
    return {"enabled": settings.ENABLE_JOB_DISCOVERY, "ready": ready,
            "provider": provider.name, "provider_configured": provider.configured,
            "scheduler_configured": bool(settings.REMINDER_WORKER_TOKEN)}


@router.get("/search")
def search_jobs(
    keywords: str = Query(min_length=1, max_length=200), location: str = Query(default="India", max_length=200),
    page: int = Query(default=1, ge=1, le=100), page_size: int = Query(default=20, ge=1, le=50),
    salary_min: int | None = Query(default=None, ge=0), job_type: str | None = Query(default=None, max_length=100),
    sort: Literal["newest", "title"] = "newest", db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_ready(db)
    enforce_request_limit("job-search", db, user.id, settings.JOB_SEARCH_REQUESTS_PER_MINUTE)
    try:
        result = _provider().search(keywords=keywords, location=location, page=page,
                                    page_size=page_size, salary_min=salary_min,
                                    job_type=job_type, sort=sort)
    except ProviderError as error:
        retry_after = str(error.retry_after or 60)
        raise HTTPException(error.status_code, str(error),
                            headers={"Retry-After": retry_after} if error.status_code == 429 else None) from None
    rows = []
    try:
        for item in result.jobs:
            if job_type and job_type.casefold() not in (item.job_type or "").casefold():
                continue
            rows.append(upsert_listing(db, item))
        db.commit()
        for row in rows:
            db.refresh(row)
    except Exception:
        db.rollback()
        raise
    saved = {value.listing_id: value.id for value in db.query(SavedJob).filter(
        SavedJob.user_id == user.id, SavedJob.listing_id.in_([row.id for row in rows] or [-1])).all()}
    if sort == "title":
        rows.sort(key=lambda row: row.title.casefold())
    else:
        rows.sort(key=lambda row: row.published_at or row.fetched_at, reverse=True)
    return {"jobs": [_listing(row, saved.get(row.id)) for row in rows], "total": result.total,
            "page": result.page, "page_size": result.page_size, "provider": result.provider,
            "partial": len(rows) < len(result.jobs)}


@router.get("/listings/{listing_id}")
def listing(listing_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_ready(db)
    row = db.query(ExternalJobListing).filter(ExternalJobListing.id == listing_id).first()
    if row is None:
        raise HTTPException(404, "Job listing not found.")
    saved = db.query(SavedJob).filter_by(user_id=user.id, listing_id=row.id).first()
    return _listing(row, saved.id if saved else None)


@router.post("/import/preview")
def import_preview(payload: ImportPreviewRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_ready(db)
    enforce_request_limit("job-import", db, user.id, settings.JOB_IMPORT_REQUESTS_PER_MINUTE)
    source_url = payload.url.strip() if payload.url else None
    try:
        if payload.manual_text and payload.manual_text.strip():
            if source_url:
                source_url, _, _ = validate_public_https_url(source_url)
            extracted = {"text": payload.manual_text.strip(), "title": "", "company": "", "location": "",
                         "application_url": source_url, "structured": False}
            source = source_url or f"manual:{fingerprint(extracted['text'])}"
            mode = "manual"
        else:
            source_url, _, _ = validate_public_https_url(source_url or "")
            if not robots_allowed(source_url):
                raise ImportUnavailableError("This site does not permit automated retrieval. Paste the description instead.")
            extracted = extract_job_text(fetch_public_page(source_url))
            source, mode = source_url, "url"
    except ImportSecurityError as error:
        raise HTTPException(422, str(error)) from None
    except ImportUnavailableError as error:
        raise HTTPException(409, str(error)) from None
    enforce_ai_usage(db, user.id)
    try:
        analysis = analyze_job_description(extracted["text"])
    except (LLMConfigurationError, LLMError) as error:
        _ai_error(error)
    return {
        "preview_token": preview_token(user.id, source), "mode": mode, "source_url": source_url,
        "structured": extracted["structured"], "title": analysis.get("title") or extracted["title"],
        "company": analysis.get("company") or extracted["company"],
        "location": analysis.get("location") or extracted["location"],
        "job_type": analysis.get("employment_type"), "salary_text": None,
        "experience_text": "; ".join(analysis.get("experience_requirements") or []) or None,
        "skills": list(dict.fromkeys((analysis.get("required_skills") or []) + (analysis.get("preferred_skills") or []))),
        "description": extracted["text"], "application_url": extracted["application_url"],
        "warnings": ["Review every extracted field before saving. Imported page content is untrusted."],
    }


@router.post("/import/save", status_code=201)
def import_save(payload: ImportSaveRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_ready(db)
    try:
        verify_preview_token(payload.preview_token, user.id)
        application_url, _, _ = validate_public_https_url(payload.application_url)
    except ImportSecurityError as error:
        raise HTTPException(422, str(error)) from None
    provider_id = fingerprint(application_url)
    item = NormalizedJob(
        provider="url_import", provider_job_id=provider_id, title=payload.title.strip(),
        company=payload.company.strip() if payload.company else None,
        location=payload.location.strip() if payload.location else None,
        job_type=payload.job_type.strip() if payload.job_type else None,
        salary_text=payload.salary_text.strip() if payload.salary_text else None,
        experience_text=payload.experience_text.strip() if payload.experience_text else None,
        skills=[value.strip() for value in payload.skills if value.strip()],
        description=payload.description.strip(), published_at=None,
        provider_url=application_url, application_url=application_url,
        normalized={"source": "User-reviewed URL import"},
    )
    try:
        listing = upsert_listing(db, item)
        existing = db.query(SavedJob).filter_by(user_id=user.id, listing_id=listing.id).first()
        if existing:
            raise HTTPException(409, "This imported job is already saved.")
        job = Job(user_id=user.id, title=item.title, company=item.company, description=item.description,
                  extracted_skills={"title": item.title, "company": item.company,
                                    "required_skills": item.skills, "preferred_skills": [],
                                    "location": item.location, "employment_type": item.job_type,
                                    "key_responsibilities": [], "source_listing_id": listing.id})
        db.add(job)
        db.flush()
        saved = SavedJob(user_id=user.id, listing_id=listing.id, job_id=job.id,
                         notes=payload.notes, tags_json=SaveJobRequest.clean_tags(payload.tags))
        db.add(saved)
        db.commit()
        db.refresh(saved)
        db.refresh(listing)
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    saved._listing = listing
    return _saved(saved)


@router.post("/saved-jobs", status_code=201)
def save_job(payload: SaveJobRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_ready(db)
    listing = db.query(ExternalJobListing).filter_by(id=payload.listing_id, is_active=True).first()
    if listing is None:
        raise HTTPException(404, "Active job listing not found.")
    if db.query(SavedJob).filter_by(user_id=user.id, listing_id=listing.id).first():
        raise HTTPException(409, "This job is already saved.")
    job = Job(user_id=user.id, title=listing.title, company=listing.company,
              description=listing.description, extracted_skills={
                  "title": listing.title, "company": listing.company,
                  "required_skills": listing.skills_json or [], "preferred_skills": [],
                  "location": listing.location, "employment_type": listing.job_type,
                  "key_responsibilities": [], "source_listing_id": listing.id,
              })
    db.add(job)
    db.flush()
    saved = SavedJob(user_id=user.id, listing_id=listing.id, job_id=job.id,
                     notes=payload.notes, tags_json=payload.tags)
    db.add(saved)
    try:
        db.commit()
        db.refresh(saved)
    except Exception:
        db.rollback()
        raise
    saved._listing = listing
    return _saved(saved)


@router.get("/saved-jobs")
def saved_jobs(
    archived: bool = False, search: str | None = Query(default=None, max_length=200),
    tag: str | None = Query(default=None, max_length=50), db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_ready(db)
    query = db.query(SavedJob, ExternalJobListing).join(ExternalJobListing, ExternalJobListing.id == SavedJob.listing_id).filter(SavedJob.user_id == user.id)
    query = query.filter(SavedJob.archived_at.is_not(None) if archived else SavedJob.archived_at.is_(None))
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(or_(ExternalJobListing.title.ilike(term), ExternalJobListing.company.ilike(term), ExternalJobListing.location.ilike(term)))
    results = []
    for saved, listing in query.order_by(SavedJob.created_at.desc(), SavedJob.id.desc()).limit(200):
        if tag and tag.casefold() not in {str(value).casefold() for value in (saved.tags_json or [])}:
            continue
        saved._listing = listing
        results.append(_saved(saved))
    return results


@router.put("/saved-jobs/{saved_id}")
def update_saved(saved_id: int, payload: SavedJobUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_ready(db)
    saved = _owned_saved(db, user.id, saved_id)
    changes = payload.model_dump(exclude_unset=True)
    if "notes" in changes:
        saved.notes = changes["notes"]
    if "tags" in changes:
        saved.tags_json = changes["tags"]
    if "archived" in changes:
        saved.archived_at = datetime.now(timezone.utc) if changes["archived"] else None
    try:
        db.commit()
        db.refresh(saved)
    except Exception:
        db.rollback()
        raise
    return _saved(saved)


@router.get("/preferences")
def preferences(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_ready(db)
    value = db.query(JobPreference).filter_by(user_id=user.id).first()
    if value is None:
        return {"id": 0, "roles": [], "locations": [], "remote_policy": "any", "experience_levels": [],
                "job_types": [], "timezone": "Asia/Calcutta", "version": 0, "updated_at": datetime.now(timezone.utc)}
    return {"id": value.id, "roles": value.roles_json or [], "locations": value.locations_json or [],
            "remote_policy": value.remote_policy, "experience_levels": value.experience_levels_json or [],
            "job_types": value.job_types_json or [], "timezone": value.timezone,
            "version": value.version, "updated_at": value.updated_at}


@router.put("/preferences")
def update_preferences(payload: PreferenceUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_ready(db)
    value = db.query(JobPreference).filter_by(user_id=user.id).first()
    if value is None:
        value = JobPreference(user_id=user.id)
        db.add(value)
    else:
        value.version += 1
    value.roles_json, value.locations_json = payload.roles, payload.locations
    value.remote_policy, value.experience_levels_json = payload.remote_policy, payload.experience_levels
    value.job_types_json, value.timezone = payload.job_types, payload.timezone
    try:
        db.commit()
        db.refresh(value)
    except Exception:
        db.rollback()
        raise
    return {"id": value.id, "roles": value.roles_json, "locations": value.locations_json,
            "remote_policy": value.remote_policy, "experience_levels": value.experience_levels_json,
            "job_types": value.job_types_json, "timezone": value.timezone,
            "version": value.version, "updated_at": value.updated_at}


@router.get("/recommendations")
def recommendations(limit: int = Query(default=20, ge=1, le=50), db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    require_ready(db)
    try:
        values = recommend(db, user.id, limit)
        db.commit()
    except Exception:
        db.rollback()
        raise
    if not values:
        return {"recommendations": [], "message": "Save and approve a resume, then search genuine listings to receive recommendations."}
    return {"recommendations": values,
            "message": "Scores explain evidence and preferences; they do not predict hiring success."}
