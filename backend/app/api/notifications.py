from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.advanced import NotificationPreference
from app.models.user import User
from app.schemas.integrations import NotificationPreferenceUpdate
from app.services.auth_service import get_current_user
from app.services.interview_engine import require_ready


router = APIRouter(prefix="/api/notifications", tags=["Notifications"])
DEFAULT_CATEGORIES = {"application": True, "interview": True, "deadline": True, "follow_up": True, "account": True}


def view(value):
    return {"categories": value.categories_json, "email_enabled": value.email_enabled,
            "timezone": value.timezone, "quiet_hours": value.quiet_hours_json,
            "version": value.version, "updated_at": value.updated_at}


@router.get("/preferences")
def get_preferences(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_ready(db)
    value = db.query(NotificationPreference).filter(NotificationPreference.user_id == user.id).first()
    if value is None:
        return {"categories": DEFAULT_CATEGORIES, "email_enabled": False, "timezone": "Asia/Calcutta",
                "quiet_hours": {}, "version": 0, "updated_at": None}
    return view(value)


@router.put("/preferences")
def put_preferences(payload: NotificationPreferenceUpdate, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    require_ready(db)
    try:
        ZoneInfo(payload.timezone)
    except ZoneInfoNotFoundError:
        raise HTTPException(422, "Use a valid IANA timezone name.") from None
    value = db.query(NotificationPreference).filter(NotificationPreference.user_id == user.id).with_for_update().first()
    if value is None:
        if payload.expected_version not in (None, 0):
            raise HTTPException(409, "Notification preferences changed elsewhere. Refresh and retry.")
        value = NotificationPreference(user_id=user.id, version=1)
        db.add(value)
    else:
        if payload.expected_version != value.version:
            raise HTTPException(409, "Notification preferences changed elsewhere. Refresh and retry.")
        value.version += 1
    value.categories_json = {**DEFAULT_CATEGORIES, **payload.categories}
    value.email_enabled = payload.email_enabled
    value.timezone = payload.timezone
    value.quiet_hours_json = payload.quiet_hours
    db.commit(); db.refresh(value)
    return view(value)
