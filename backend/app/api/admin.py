from fastapi import APIRouter, Depends, Header
from sqlalchemy import func, inspect, text
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.advanced import AdminAuditEvent, InterviewSession
from app.models.discovery import Application, Notification, Reminder
from app.models.user import User
from app.services.admin_service import audit, require_admin


router = APIRouter(prefix="/api/admin", tags=["Administration"])


def _job_provider_configured() -> bool:
    if settings.JOB_PROVIDER.casefold() == "himalayas":
        return bool(settings.HIMALAYAS_API_KEY.strip())
    if settings.JOB_PROVIDER.casefold() == "jooble":
        return bool(settings.JOOBLE_API_KEY.strip())
    return False


@router.get("/overview")
def overview(x_request_id: str | None = Header(default=None), db: Session = Depends(get_db),
             admin: User = Depends(require_admin)):
    tables = set(inspect(db.connection()).get_table_names())
    counts = {"users": db.query(func.count(User.id)).scalar() or 0}
    for label, model in (("applications", Application), ("interview_sessions", InterviewSession),
                         ("reminders", Reminder), ("notifications", Notification)):
        counts[label] = (db.query(func.count(model.id)).scalar() or 0) if model.__tablename__ in tables else 0
    db_ok = db.execute(text("SELECT 1")).scalar_one() == 1
    audit(db, admin.id, "admin.overview.viewed", metadata={"status": "ok", "count": sum(counts.values())}, request_id=x_request_id)
    db.commit()
    return {"health": {"database": "ok" if db_ok else "unavailable"}, "counts": counts,
            "providers": {"gemini_configured": bool(settings.LLM_API_KEY.strip() and settings.LLM_API_KEY != "dev_llm_key"),
                "job_provider": settings.JOB_PROVIDER, "job_provider_configured": _job_provider_configured(),
                "gmail_enabled": settings.ENABLE_GMAIL},
            "privacy": "Operational aggregates only. Private resumes, answers, emails, and credentials are excluded."}


@router.get("/audit-events")
def events(limit: int = 50, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    limit = max(1, min(limit, 100))
    rows = db.query(AdminAuditEvent).order_by(AdminAuditEvent.occurred_at.desc(), AdminAuditEvent.id.desc()).limit(limit).all()
    return [{"id": row.id, "actor_user_id": row.actor_user_id, "action": row.action,
             "target_type": row.target_type, "target_id": row.target_id,
             "metadata": row.metadata_json, "request_id": row.request_id,
             "occurred_at": row.occurred_at} for row in rows]
