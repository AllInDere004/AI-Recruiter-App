from datetime import datetime, timezone

from fastapi import HTTPException

from app.models.discovery import Application, ApplicationEvent, SavedJob
from app.models.intelligence import GenerationVersion, ResumeVersion


STATUSES = ("Saved", "Preparing", "Applied", "Assessment", "Interview", "Offer", "Rejected", "Withdrawn")
TRANSITIONS = {
    "Saved": {"Preparing", "Applied", "Withdrawn"},
    "Preparing": {"Saved", "Applied", "Withdrawn"},
    "Applied": {"Assessment", "Interview", "Offer", "Rejected", "Withdrawn"},
    "Assessment": {"Interview", "Offer", "Rejected", "Withdrawn"},
    "Interview": {"Assessment", "Offer", "Rejected", "Withdrawn"},
    "Offer": {"Withdrawn"},
    "Rejected": set(),
    "Withdrawn": set(),
}


def event(db, *, user_id: int, application_id: int, event_type: str,
          from_status: str | None = None, to_status: str | None = None, context: dict | None = None):
    safe = {str(key)[:100]: value for key, value in (context or {}).items()
            if isinstance(value, (str, int, float, bool, type(None)))}
    db.add(ApplicationEvent(user_id=user_id, application_id=application_id, event_type=event_type,
                            from_status=from_status, to_status=to_status, context_json=safe))


def owned_application(db, user_id: int, application_id: int, *, lock: bool = False) -> Application:
    query = db.query(Application).filter(Application.id == application_id, Application.user_id == user_id)
    if lock:
        query = query.with_for_update()
    value = query.first()
    if value is None:
        raise HTTPException(404, "Application not found.")
    return value


def create_application(db, user_id: int, saved_job_id: int, notes: str | None = None) -> Application:
    saved = db.query(SavedJob).filter(SavedJob.id == saved_job_id, SavedJob.user_id == user_id).first()
    if saved is None:
        raise HTTPException(404, "Saved job not found.")
    existing = db.query(Application).filter_by(user_id=user_id, saved_job_id=saved.id).first()
    if existing:
        raise HTTPException(409, "An application already exists for this saved job.")
    value = Application(user_id=user_id, saved_job_id=saved.id, job_id=saved.job_id,
                        status="Saved", notes=notes)
    db.add(value)
    db.flush()
    event(db, user_id=user_id, application_id=value.id, event_type="application_created",
          to_status="Saved", context={"saved_job_id": saved.id})
    return value


def _approved_resume(db, user_id: int, version_id: int | None):
    if version_id is None:
        return
    value = db.query(ResumeVersion).filter_by(id=version_id, user_id=user_id, approved=True).first()
    if value is None:
        raise HTTPException(409, "The selected resume version is not owned and approved.")


def _approved_document(db, user_id: int, version_id: int | None, kind: str):
    if version_id is None:
        return
    value = db.query(GenerationVersion).filter_by(id=version_id, user_id=user_id, approved=True, kind=kind).first()
    if value is None:
        raise HTTPException(409, f"The selected {kind.replace('_', ' ')} version is not owned and approved.")


def update_application(db, user_id: int, application_id: int, payload) -> Application:
    value = owned_application(db, user_id, application_id, lock=True)
    if value.version != payload.expected_version:
        raise HTTPException(409, "This application changed elsewhere. Refresh and retry.")
    changes = payload.model_dump(exclude_unset=True)
    new_status = changes.pop("status", None)
    confirmed = bool(changes.pop("confirm_submission", False))
    old_status = value.status
    if new_status and new_status != old_status:
        if new_status not in TRANSITIONS.get(old_status, set()):
            raise HTTPException(409, f"Cannot move an application from {old_status} to {new_status}.")
        if new_status == "Applied" and not confirmed:
            raise HTTPException(409, "Confirm that you submitted the external application before marking it Applied.")
        value.status = new_status
        if new_status == "Applied":
            value.submitted_at = datetime.now(timezone.utc)
            value.application_date = changes.get("application_date") or value.submitted_at
        event(db, user_id=user_id, application_id=value.id, event_type="status_changed",
              from_status=old_status, to_status=new_status,
              context={"submission_confirmed": new_status == "Applied"})
    _approved_resume(db, user_id, changes.get("resume_version_id"))
    _approved_document(db, user_id, changes.get("email_version_id"), "email")
    _approved_document(db, user_id, changes.get("cover_letter_version_id"), "cover_letter")
    editable = {"application_date", "recruiter_name", "recruiter_email", "notes", "interview_at",
                "deadline_at", "resume_version_id", "email_version_id", "cover_letter_version_id"}
    changed_fields = []
    for field in editable:
        if field in changes and getattr(value, field) != changes[field]:
            setattr(value, field, changes[field])
            changed_fields.append(field)
    if changed_fields:
        event(db, user_id=user_id, application_id=value.id, event_type="application_updated",
              context={"fields": ",".join(sorted(changed_fields))})
    value.version += 1
    value.updated_at = datetime.now(timezone.utc)
    db.flush()
    return value
