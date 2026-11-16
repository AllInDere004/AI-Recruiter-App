from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import distinct, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.discovery import (
    Application, ApplicationEvent, ExternalJobListing, Notification, Reminder, SavedJob,
)
from app.models.user import User
from app.models.intelligence import CareerReport
from app.schemas.discovery import (
    ApplicationCreate, ApplicationUpdate, NotificationUpdate, ReminderCreate, ReminderUpdate,
)
from app.services.application_service import create_application, owned_application, update_application
from app.services.auth_service import get_current_user
from app.services.discovery_repository import require_ready
from app.services.reminders import authorize_worker, create_reminder, owned_reminder, process_due, update_reminder


router = APIRouter(prefix="/api/applications", tags=["Applications and reminders"])


def _application(value, listing=None):
    return {
        "id": value.id, "saved_job_id": value.saved_job_id, "job_id": value.job_id,
        "status": value.status, "submitted_at": value.submitted_at,
        "application_date": value.application_date, "recruiter_name": value.recruiter_name,
        "recruiter_email": value.recruiter_email, "notes": value.notes,
        "interview_at": value.interview_at, "deadline_at": value.deadline_at,
        "resume_version_id": value.resume_version_id, "email_version_id": value.email_version_id,
        "cover_letter_version_id": value.cover_letter_version_id, "version": value.version,
        "created_at": value.created_at, "updated_at": value.updated_at,
        "job": None if listing is None else {"listing_id": listing.id, "title": listing.title,
            "company": listing.company, "location": listing.location,
            "application_url": listing.application_url, "provider": listing.provider},
    }


def _reminder(value):
    state = value.state
    now = datetime.now(timezone.utc)
    due = value.snoozed_until if state == "snoozed" and value.snoozed_until else value.due_at
    if due and due.tzinfo is None:
        due = due.replace(tzinfo=timezone.utc)
    if state in {"upcoming", "snoozed"} and due and due <= now:
        state = "overdue"
    return {"id": value.id, "application_id": value.application_id, "kind": value.kind,
            "title": value.title, "note": value.note, "due_at": value.due_at,
            "timezone": value.timezone, "state": state, "snoozed_until": value.snoozed_until,
            "completed_at": value.completed_at, "dismissed_at": value.dismissed_at,
            "attempts": value.attempts, "version": value.version,
            "created_at": value.created_at, "updated_at": value.updated_at}


@router.post("/", status_code=201)
def create(payload: ApplicationCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_ready(db)
    try:
        value = create_application(db, user.id, payload.saved_job_id, payload.notes)
        db.commit()
        db.refresh(value)
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    return _application(value)


@router.get("/")
def list_applications(
    status: str | None = Query(default=None, max_length=30), search: str | None = Query(default=None, max_length=200),
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    require_ready(db)
    query = db.query(Application, ExternalJobListing).join(SavedJob, SavedJob.id == Application.saved_job_id).join(
        ExternalJobListing, ExternalJobListing.id == SavedJob.listing_id).filter(Application.user_id == user.id)
    if status:
        query = query.filter(Application.status == status)
    if search:
        term = f"%{search.strip()}%"
        query = query.filter((ExternalJobListing.title.ilike(term)) | (ExternalJobListing.company.ilike(term)))
    return [_application(value, listing) for value, listing in query.order_by(Application.updated_at.desc(), Application.id.desc()).limit(500)]


@router.get("/{application_id}")
def get_application(application_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_ready(db)
    value = owned_application(db, user.id, application_id)
    listing = db.query(ExternalJobListing).join(SavedJob, SavedJob.listing_id == ExternalJobListing.id).filter(
        SavedJob.id == value.saved_job_id, SavedJob.user_id == user.id).one()
    return _application(value, listing)


@router.put("/{application_id}")
def update(application_id: int, payload: ApplicationUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_ready(db)
    try:
        value = update_application(db, user.id, application_id, payload)
        db.commit()
        db.refresh(value)
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    return _application(value)


@router.post("/reminders", status_code=201)
def add_reminder(payload: ReminderCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_ready(db)
    try:
        value = create_reminder(db, user.id, payload)
        db.commit()
        db.refresh(value)
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    return _reminder(value)


@router.get("/reminders/list")
def list_reminders(state: str | None = Query(default=None, max_length=30), db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    require_ready(db)
    query = db.query(Reminder).filter(Reminder.user_id == user.id)
    if state and state != "overdue":
        query = query.filter(Reminder.state == state)
    values = [_reminder(value) for value in query.order_by(Reminder.due_at, Reminder.id).limit(500)]
    return [value for value in values if not state or value["state"] == state]


@router.put("/reminders/{reminder_id}")
def change_reminder(reminder_id: int, payload: ReminderUpdate, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    require_ready(db)
    try:
        value = update_reminder(db, user.id, reminder_id, payload)
        db.commit()
        db.refresh(value)
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    return _reminder(value)


@router.post("/reminders/process-mine")
def process_my_reminders(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_ready(db)
    try:
        delivered = process_due(db, user_id=user.id, limit=100)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"delivered": delivered}


@router.post("/internal/process-reminders")
def process_reminders_worker(x_reminder_worker_token: str | None = Header(default=None),
                             db: Session = Depends(get_db)):
    require_ready(db)
    authorize_worker(x_reminder_worker_token)
    try:
        delivered = process_due(db, limit=500)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"delivered": delivered}


@router.get("/notifications/list")
def notifications(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_ready(db)
    rows = db.query(Notification).filter(Notification.user_id == user.id).order_by(
        Notification.created_at.desc(), Notification.id.desc()).limit(200).all()
    return [{"id": row.id, "reminder_id": row.reminder_id, "type": row.notification_type,
             "title": row.title, "message": row.message, "read_at": row.read_at,
             "dismissed_at": row.dismissed_at, "created_at": row.created_at} for row in rows]


@router.put("/notifications/{notification_id}")
def update_notification(notification_id: int, payload: NotificationUpdate, db: Session = Depends(get_db),
                        user: User = Depends(get_current_user)):
    require_ready(db)
    value = db.query(Notification).filter_by(id=notification_id, user_id=user.id).first()
    if value is None:
        raise HTTPException(404, "Notification not found.")
    now = datetime.now(timezone.utc)
    if payload.read is not None:
        value.read_at = now if payload.read else None
    if payload.dismissed is not None:
        value.dismissed_at = now if payload.dismissed else None
    try:
        db.commit()
        db.refresh(value)
    except Exception:
        db.rollback()
        raise
    return {"id": value.id, "read_at": value.read_at, "dismissed_at": value.dismissed_at}


@router.get("/activity/list")
def activity(
    event_type: str | None = Query(default=None, max_length=50), page: int = Query(default=1, ge=1),
    page_size: int = Query(default=30, ge=1, le=100), db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_ready(db)
    query = db.query(ApplicationEvent).filter(ApplicationEvent.user_id == user.id)
    if event_type:
        query = query.filter(ApplicationEvent.event_type == event_type)
    total = query.count()
    rows = query.order_by(ApplicationEvent.occurred_at.desc(), ApplicationEvent.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"events": [{"id": row.id, "application_id": row.application_id,
            "event_type": row.event_type, "from_status": row.from_status, "to_status": row.to_status,
            "context": row.context_json, "occurred_at": row.occurred_at} for row in rows],
            "total": total, "page": page, "page_size": page_size}


@router.get("/analytics/summary")
def analytics(
    date_from: datetime | None = None, date_to: datetime | None = None,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    require_ready(db)
    applications = db.query(Application).filter(Application.user_id == user.id)
    if date_from:
        applications = applications.filter(Application.created_at >= date_from)
    if date_to:
        applications = applications.filter(Application.created_at < date_to)
    total = applications.count()
    state_counts = {status: count for status, count in applications.with_entities(
        Application.status, func.count(Application.id)).group_by(Application.status).all()}
    submitted_ids = [row[0] for row in applications.with_entities(Application.id).filter(Application.submitted_at.is_not(None)).all()]
    submitted = len(submitted_ids)
    def reached(states):
        if not submitted_ids:
            return 0
        return db.query(func.count(distinct(ApplicationEvent.application_id))).filter(
            ApplicationEvent.user_id == user.id, ApplicationEvent.application_id.in_(submitted_ids),
            ApplicationEvent.to_status.in_(states)).scalar() or 0
    responses = reached(["Assessment", "Interview", "Offer", "Rejected"])
    interviews = reached(["Interview"])
    offers = reached(["Offer"])
    rejections = reached(["Rejected"])
    weekly = db.query(func.date(Application.created_at), func.count(Application.id)).filter(
        Application.user_id == user.id)
    if date_from:
        weekly = weekly.filter(Application.created_at >= date_from)
    if date_to:
        weekly = weekly.filter(Application.created_at < date_to)
    trend = [{"date": str(day), "applications": count} for day, count in weekly.group_by(func.date(Application.created_at)).order_by(func.date(Application.created_at)).all()]
    job_ids = [row[0] for row in applications.with_entities(Application.job_id).filter(Application.job_id.is_not(None)).all()]
    reports = db.query(CareerReport.result_json).filter(CareerReport.user_id == user.id,
        CareerReport.kind == "match", CareerReport.job_id.in_(job_ids or [-1])).all()
    scores = [row[0].get("overall_score") for row in reports if isinstance(row[0], dict) and isinstance(row[0].get("overall_score"), (int, float))]
    return {"total_applications": total, "submitted_applications": submitted,
            "interviews": interviews, "offers": offers, "rejections": rejections,
            "response_rate": round(responses * 100 / submitted, 1) if submitted else None,
            "interview_rate": round(interviews * 100 / submitted, 1) if submitted else None,
            "offer_rate": round(offers * 100 / submitted, 1) if submitted else None,
            "state_counts": state_counts, "weekly_trend": trend,
            "average_match_score": round(sum(scores) / len(scores), 1) if scores else None,
            "definitions": {"denominator": "Applications explicitly confirmed submitted in the selected range.",
                "response": "First assessment, interview, offer, or rejection transition per submitted application.",
                "empty": "Rates are null when no submitted applications exist."}}
