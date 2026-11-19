"""Opt-in, owner-scoped Phase 2 reports and immutable document history."""
from collections import OrderedDict, deque
from datetime import datetime, timezone
from threading import Lock
from time import monotonic
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.draft import Draft
from app.models.intelligence import CareerReport, GenerationVersion, ResumeVersion
from app.models.job import Job
from app.models.user import User
from app.services.auth_service import get_current_user
from app.services.career_repository import commit, fingerprint, owned, require_ready, resume_source, schema_ready, snapshot_profile
from app.services.llm_client import LLMConfigurationError, LLMError


router = APIRouter(prefix="/api/intelligence", tags=["Career intelligence"])
_requests = OrderedDict()
_request_lock = Lock()


def _throttle(user_id: int):
    """Bounded single-process safeguard, not a distributed deployment quota."""
    now = monotonic()
    with _request_lock:
        queue = _requests.setdefault(user_id, deque())
        while queue and queue[0] <= now - 60:
            queue.popleft()
        if len(queue) >= settings.CAREER_AI_REQUESTS_PER_MINUTE:
            raise HTTPException(429, "Too many AI requests. Wait a minute and retry.", headers={"Retry-After": "60"})
        queue.append(now)
        _requests.move_to_end(user_id)
        while len(_requests) > 1024:
            _requests.popitem(last=False)


class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SnapshotRequest(RequestModel):
    approved: bool = False


class AnalyzeRequest(RequestModel):
    job_id: int | None = Field(default=None, gt=0)
    resume_version_id: int | None = Field(default=None, gt=0)
    weights: dict[str, float] | None = None
    include_explanation: bool = False


class GenerateRequest(RequestModel):
    job_id: int = Field(gt=0)
    kind: Literal["tailored_resume", "cover_letter", "email"]
    parent_id: int | None = Field(default=None, gt=0)
    tone: Literal["professional", "concise", "enthusiastic"] = "professional"
    situation: str = Field(default="apply", min_length=1, max_length=100)


class DocumentUpdate(RequestModel):
    body: str | None = Field(default=None, min_length=1, max_length=100000)
    subject_line: str | None = Field(default=None, max_length=500)
    approved: bool | None = None

    @field_validator("body", "subject_line")
    @classmethod
    def text_is_not_null(cls, value):
        if value is None:
            raise ValueError("Provided document text cannot be null.")
        return value


def _resume(value):
    return {"id": value.id, "revision": value.revision, "parent_id": value.parent_id,
            "approved": value.approved, "fingerprint": value.fingerprint,
            "data": value.data_json, "metadata": value.source_metadata_json,
            "created_at": value.created_at}


def _report(value):
    return {"id": value.id, "job_id": value.job_id, "resume_version_id": value.resume_version_id,
            "kind": value.kind, "algorithm_version": value.algorithm_version,
            "profile_version": value.profile_version, "job_version": value.job_version,
            "result": value.result_json, "created_at": value.created_at}


def _document(value):
    return {"id": value.id, "user_id": value.user_id, "resume_version_id": value.resume_version_id,
            "job_id": value.job_id, "draft_id": value.draft_id, "lineage_id": value.lineage_id,
            "revision": value.revision, "parent_id": value.parent_id, "kind": value.kind,
            "content": value.content_json, "warnings": value.warnings_json,
            "approved": value.approved, "model": value.model, "created_at": value.created_at}


def _approved_resume(db, user_id: int, version_id=None):
    if version_id is not None:
        version = owned(db, ResumeVersion, user_id, version_id)
    else:
        version = db.query(ResumeVersion).filter(ResumeVersion.user_id == user_id).order_by(ResumeVersion.revision.desc()).first()
    if version is None or not version.approved:
        raise HTTPException(409, "Review and approve your current resume before analysis or generation.")
    return version


def _leaf(db, version):
    if db.query(GenerationVersion.id).filter(GenerationVersion.parent_id == version.id).first():
        raise HTTPException(409, "A newer document version exists. Refresh and edit its latest version.")


def _llm_error(error):
    if isinstance(error, LLMConfigurationError):
        raise HTTPException(503, str(error)) from None
    code = getattr(error, "provider_status", None)
    status = 429 if code == 429 else 503 if code in {408, 500, 502, 503, 504} else 502
    raise HTTPException(status, str(error)) from None


@router.get("/status")
def status(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return {"enabled": settings.ENABLE_CAREER_INTELLIGENCE,
            "ready": bool(settings.ENABLE_CAREER_INTELLIGENCE and schema_ready(db))}


@router.post("/resumes")
def create_resume(payload: SnapshotRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_ready(db)
    try:
        version = snapshot_profile(db, user.id, approved=payload.approved)
        commit(db)
        db.refresh(version)
        return _resume(version)
    except Exception:
        db.rollback()
        raise


@router.get("/resumes")
def resumes(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_ready(db)
    return [_resume(v) for v in db.query(ResumeVersion).filter(ResumeVersion.user_id == user.id).order_by(ResumeVersion.revision.desc()).limit(100)]


@router.get("/resumes/{resume_id}/source")
def original_source(resume_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_ready(db)
    version = owned(db, ResumeVersion, user.id, resume_id)
    return JSONResponse(content={"resume_version_id": version.id, "source_text": resume_source(db, version)},
                        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


@router.post("/analyze")
def analyze(payload: AnalyzeRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_ready(db)
    from app.services.career_intelligence import ALGORITHM_VERSION, analyze_ats, analyze_career
    version = _approved_resume(db, user.id, payload.resume_version_id)
    source_text = resume_source(db, version)
    job = owned(db, Job, user.id, payload.job_id) if payload.job_id else None
    kind = "match" if job else "ats"
    job_data = (job.extracted_skills or {}) if job else {}
    job_hash = fingerprint({"id": job.id, "description": job.description, "data": job_data}) if job else fingerprint(None)
    digest = fingerprint({"resume": version.fingerprint, "job": job_hash, "weights": payload.weights, "explanation": payload.include_explanation})
    existing = db.query(CareerReport).filter_by(user_id=user.id, kind=kind, algorithm_version=ALGORITHM_VERSION, input_hash=digest).first()
    if existing:
        return _report(existing)
    try:
        result = analyze_career(version.data_json, job_data, source_text, job.description, payload.weights) if job else {
            "algorithm_version": ALGORITHM_VERSION, "ats": analyze_ats(source_text, version.data_json),
            "overall_score": None, "categories": [], "requirements": [], "gaps": [], "mandatory_unmet": [],
            "disclaimer": "ATS readiness is a heuristic, not a promise of employer acceptance.",
        }
    except ValueError:
        raise HTTPException(422, "Analysis inputs or scoring weights are invalid.") from None
    if payload.include_explanation and job:
        from app.services.document_generation import explain_gaps
        _throttle(user.id)
        try:
            result["gap_explanation"] = explain_gaps(result)
        except LLMError as error:
            _llm_error(error)
    result["profile_version"] = version.fingerprint
    result["job_version"] = job_hash
    record = CareerReport(user_id=user.id, resume_version_id=version.id, job_id=job.id if job else None,
        kind=kind, algorithm_version=ALGORITHM_VERSION, profile_version=version.fingerprint,
        job_version=job_hash, input_hash=digest, result_json=result)
    db.add(record)
    commit(db)
    db.refresh(record)
    return _report(record)


@router.get("/reports")
def reports(job_id: int | None = Query(default=None, gt=0), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_ready(db)
    query = db.query(CareerReport).filter(CareerReport.user_id == user.id)
    if job_id is not None:
        owned(db, Job, user.id, job_id)
        query = query.filter(CareerReport.job_id == job_id)
    return [_report(v) for v in query.order_by(CareerReport.created_at.desc(), CareerReport.id.desc()).limit(100)]


@router.get("/reports/{report_id}")
def report(report_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_ready(db)
    return _report(owned(db, CareerReport, user.id, report_id))


@router.post("/documents/generate")
def generate(payload: GenerateRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_ready(db)
    from app.services.document_generation import generate_document
    job = owned(db, Job, user.id, payload.job_id)
    version = _approved_resume(db, user.id)
    parent = owned(db, GenerationVersion, user.id, payload.parent_id) if payload.parent_id else None
    if parent:
        _leaf(db, parent)
        if parent.job_id != job.id or parent.kind != payload.kind:
            raise HTTPException(422, "The parent must belong to the same job and document type.")
    _throttle(user.id)
    try:
        result = generate_document(payload.kind, version.data_json, resume_source(db, version), job.extracted_skills or {}, job.description,
                                   tone=payload.tone, situation=payload.situation)
    except LLMError as error:
        _llm_error(error)
    except ValueError:
        raise HTTPException(422, "The generated document contains unsupported facts and could not be saved.") from None
    record = GenerationVersion(user_id=user.id, resume_version_id=version.id, job_id=job.id,
        draft_id=parent.draft_id if parent else None, lineage_id=parent.lineage_id if parent else str(uuid4()),
        revision=parent.revision + 1 if parent else 1, parent_id=parent.id if parent else None,
        kind=payload.kind, content_json=result["content"], warnings_json=result.get("warnings", []),
        approved=False, model=settings.LLM_MODEL)
    db.add(record)
    commit(db)
    db.refresh(record)
    return _document(record)


@router.get("/documents")
def documents(job_id: int | None = Query(default=None, gt=0), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_ready(db)
    query = db.query(GenerationVersion).filter(GenerationVersion.user_id == user.id)
    if job_id is not None:
        owned(db, Job, user.id, job_id)
        query = query.filter(GenerationVersion.job_id == job_id)
    return [_document(v) for v in query.order_by(GenerationVersion.created_at.desc(), GenerationVersion.id.desc()).limit(100)]


def _approve_email(db, version, user_id):
    job = owned(db, Job, user_id, version.job_id)
    draft = owned(db, Draft, user_id, version.draft_id) if version.draft_id else None
    if draft and draft.job_id != job.id:
        raise HTTPException(409, "The saved draft belongs to another job.")
    if draft is None:
        draft = Draft(user_id=user_id, job_id=job.id, situation="apply", tone="professional", status="Draft")
        db.add(draft)
    draft.subject_line = version.content_json.get("subject_line")
    draft.body = version.content_json["body"]
    draft.match_score = None
    draft.updated_at = datetime.now(timezone.utc)
    db.flush()
    version.draft_id = draft.id


@router.put("/documents/{document_id}")
def edit(document_id: int, payload: DocumentUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_ready(db)
    from app.services.document_generation import validate_document_edit
    original = owned(db, GenerationVersion, user.id, document_id)
    _leaf(db, original)
    source = owned(db, ResumeVersion, user.id, original.resume_version_id)
    job = owned(db, Job, user.id, original.job_id)
    changes = payload.model_dump(exclude_unset=True)
    if not changes or ("approved" in changes and changes["approved"] is None):
        raise HTTPException(422, "Provide document changes or an explicit approval choice.")
    content = dict(original.content_json)
    content.update({k: v for k, v in changes.items() if k in {"body", "subject_line"}})
    try:
        warnings = validate_document_edit(original.kind, content, resume_source(db, source), job.extracted_skills or {})
    except ValueError:
        raise HTTPException(422, "This document contains unsupported candidate facts. Correct them before approval or export.") from None
    changed = content != original.content_json
    if changed:
        # The new wording is user-authored, not the model's prior evidence selection.
        content["evidence_ids"] = []
        content["policy_version"] = "user-edited-v1"
        record = GenerationVersion(user_id=user.id, resume_version_id=source.id, job_id=job.id,
            draft_id=original.draft_id, lineage_id=original.lineage_id, revision=original.revision + 1,
            parent_id=original.id, kind=original.kind, content_json=content, warnings_json=warnings,
            approved=False, model=original.model)
        db.add(record)
    else:
        record = original
    if changes.get("approved") is True:
        if not source.approved:
            raise HTTPException(409, "The source resume must be reviewed before document approval.")
        record.approved = True
        record.warnings_json = warnings
        if record.kind == "email":
            _approve_email(db, record, user.id)
    elif "approved" in changes:
        record.approved = False
    commit(db)
    db.refresh(record)
    return _document(record)


@router.get("/documents/{document_id}/export")
def export(document_id: int, format: Literal["pdf", "docx"] = "pdf", db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_ready(db)
    from app.services.document_generation import render_document, validate_document_edit
    version = owned(db, GenerationVersion, user.id, document_id)
    source = owned(db, ResumeVersion, user.id, version.resume_version_id)
    job = owned(db, Job, user.id, version.job_id)
    if not version.approved or not source.approved:
        raise HTTPException(409, "Review and approve this document before downloading it.")
    try:
        validate_document_edit(version.kind, version.content_json, resume_source(db, source), job.extracted_skills or {})
        content, mime, filename = render_document(version.content_json, format)
    except ValueError:
        raise HTTPException(422, "This document could not be safely exported. Review its content.") from None
    return Response(content=content, media_type=mime, headers={
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff",
    })
