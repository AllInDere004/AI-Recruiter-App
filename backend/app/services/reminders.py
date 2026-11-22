import hmac
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException

from app.config import settings
from app.models.discovery import Notification, Reminder
from app.models.advanced import NotificationPreference
from app.services.application_service import event, owned_application


def utc_datetime(value: datetime, timezone_name: str) -> datetime:
    try:
        ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        raise HTTPException(422, "Use a valid IANA timezone name.") from None
    if value.tzinfo is None or value.utcoffset() is None:
        raise HTTPException(422, "Reminder times must include a UTC offset.")
    return value.astimezone(timezone.utc)


def owned_reminder(db, user_id: int, reminder_id: int, *, lock: bool = False) -> Reminder:
    query = db.query(Reminder).filter(Reminder.id == reminder_id, Reminder.user_id == user_id)
    if lock:
        query = query.with_for_update()
    value = query.first()
    if value is None:
        raise HTTPException(404, "Reminder not found.")
    return value


def create_reminder(db, user_id: int, payload) -> Reminder:
    if payload.application_id:
        owned_application(db, user_id, payload.application_id)
    due_at = utc_datetime(payload.due_at, payload.timezone)
    value = Reminder(user_id=user_id, application_id=payload.application_id, kind=payload.kind,
                     title=payload.title.strip(), note=payload.note, due_at=due_at,
                     timezone=payload.timezone, delivery_key=f"reminder:{uuid4()}")
    db.add(value)
    db.flush()
    if value.application_id:
        event(db, user_id=user_id, application_id=value.application_id,
              event_type="reminder_created", context={"reminder_id": value.id, "kind": value.kind})
    return value


def update_reminder(db, user_id: int, reminder_id: int, payload) -> Reminder:
    value = owned_reminder(db, user_id, reminder_id, lock=True)
    if value.version != payload.expected_version:
        raise HTTPException(409, "This reminder changed elsewhere. Refresh and retry.")
    now = datetime.now(timezone.utc)
    if payload.action == "complete":
        value.state, value.completed_at = "completed", now
    elif payload.action == "dismiss":
        value.state, value.dismissed_at = "dismissed", now
    else:
        if payload.snoozed_until is None:
            raise HTTPException(422, "Choose a snooze time.")
        snooze = utc_datetime(payload.snoozed_until, value.timezone)
        if snooze <= now:
            raise HTTPException(422, "The snooze time must be in the future.")
        value.state, value.snoozed_until = "snoozed", snooze
    value.version += 1
    value.updated_at = now
    if value.application_id:
        event(db, user_id=user_id, application_id=value.application_id,
              event_type=f"reminder_{payload.action}", context={"reminder_id": value.id})
    db.flush()
    return value


def _effective_due(reminder: Reminder):
    return reminder.snoozed_until if reminder.state == "snoozed" and reminder.snoozed_until else reminder.due_at


def process_due(db, *, user_id: int | None = None, limit: int = 100) -> int:
    now = datetime.now(timezone.utc)
    query = db.query(Reminder).filter(Reminder.state.in_(["upcoming", "snoozed"]))
    if user_id is not None:
        query = query.filter(Reminder.user_id == user_id)
    candidates = query.order_by(Reminder.due_at, Reminder.id).with_for_update(skip_locked=True).limit(limit).all()
    delivered = 0
    for value in candidates:
        due = _effective_due(value)
        if due.tzinfo is None:
            due = due.replace(tzinfo=timezone.utc)
        if due > now:
            continue
        key = f"{value.delivery_key}:due:{due.astimezone(timezone.utc).isoformat()}"
        value.lease_token = str(uuid4())
        value.lease_until = now + timedelta(minutes=2)
        value.attempts += 1
        preference = db.query(NotificationPreference).filter(NotificationPreference.user_id == value.user_id).first()
        enabled = True if preference is None else bool((preference.categories_json or {}).get(value.kind, True))
        exists = db.query(Notification.id).filter(Notification.delivery_key == key).first()
        if enabled and not exists:
            db.add(Notification(user_id=value.user_id, reminder_id=value.id,
                                notification_type=value.kind, title=value.title,
                                message=value.note or "A saved reminder is due.", delivery_key=key))
            delivered += 1
        value.state = "overdue"
        value.lease_token = None
        value.lease_until = None
        value.version += 1
        if value.application_id:
            event(db, user_id=value.user_id, application_id=value.application_id,
                  event_type="reminder_due", context={"reminder_id": value.id})
    db.flush()
    return delivered


def authorize_worker(token: str | None):
    configured = settings.REMINDER_WORKER_TOKEN
    if not configured or not token or not hmac.compare_digest(configured, token):
        raise HTTPException(401, "Reminder worker authorization failed.")
