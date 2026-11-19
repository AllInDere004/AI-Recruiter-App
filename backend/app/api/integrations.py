import hashlib
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.advanced import EmailSendRecord, GmailConnection
from app.models.intelligence import GenerationVersion
from app.models.user import User
from app.schemas.integrations import GmailSendApproval, OAuthCallback
from app.services.auth_service import get_current_user
from app.services.gmail_service import configured, finish_oauth, schema_ready, send_message, start_oauth


router = APIRouter(prefix="/api/integrations", tags=["Integrations"])


@router.get("/gmail/status")
def status(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ready = schema_ready(db)
    connection = db.query(GmailConnection).filter(GmailConnection.user_id == user.id,
        GmailConnection.revoked_at.is_(None)).first() if ready else None
    return {"enabled": configured(), "ready": ready, "connected": connection is not None,
            "email_hint": connection.email_hint if connection else None,
            "scopes": connection.scopes_json if connection else [],
            "privacy": "Gmail is optional. Emails are sent only after explicit review and approval."}


@router.post("/gmail/authorize")
def authorize(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return {"authorization_url": start_oauth(db, user.id)}


@router.post("/gmail/callback")
def callback(payload: OAuthCallback, db: Session = Depends(get_db)):
    value = finish_oauth(db, payload.state, payload.code)
    return {"connected": True, "email_hint": value.email_hint, "scopes": value.scopes_json}


@router.delete("/gmail")
def disconnect(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    value = db.query(GmailConnection).filter(GmailConnection.user_id == user.id).with_for_update().first()
    if value is not None:
        value.revoked_at = datetime.now(timezone.utc)
        value.encrypted_refresh_token = "revoked"
        db.commit()
    return {"connected": False}


@router.post("/gmail/send")
def send(payload: GmailSendApproval, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not configured() or not schema_ready(db):
        raise HTTPException(503, "Gmail integration is disabled or not configured.")
    previous = db.query(EmailSendRecord).filter(EmailSendRecord.idempotency_key == payload.idempotency_key,
        EmailSendRecord.user_id == user.id).first()
    if previous:
        return {"status": previous.status, "send_record_id": previous.id, "duplicate": True}
    document = db.query(GenerationVersion).filter(GenerationVersion.id == payload.generation_version_id,
        GenerationVersion.user_id == user.id, GenerationVersion.kind == "email",
        GenerationVersion.approved.is_(True)).first()
    if document is None:
        raise HTTPException(404, "Approved email draft not found.")
    content = document.content_json or {}
    if payload.subject != (content.get("subject_line") or "") or payload.body != (content.get("body") or ""):
        raise HTTPException(409, "The email changed after approval. Review and approve the saved draft again.")
    connection = db.query(GmailConnection).filter(GmailConnection.user_id == user.id,
        GmailConnection.revoked_at.is_(None)).first()
    if connection is None:
        raise HTTPException(409, "Connect Gmail before sending.")
    now = datetime.now(timezone.utc)
    record = EmailSendRecord(user_id=user.id, generation_version_id=document.id,
        recipient_hash=hashlib.sha256(str(payload.recipient).casefold().encode()).hexdigest(),
        subject_hash=hashlib.sha256(payload.subject.encode()).hexdigest(), status="approved",
        approved_at=now, idempotency_key=payload.idempotency_key)
    db.add(record); db.flush()
    try:
        result = send_message(connection, str(payload.recipient), payload.subject, payload.body)
        record.provider_message_id = str(result.get("id", ""))[:255] or None
        record.status = "sent"; record.sent_at = datetime.now(timezone.utc)
    except HTTPException as error:
        record.status = "failed"; record.error_category = "provider"
        db.commit()
        raise error
    db.commit(); db.refresh(record)
    return {"status": record.status, "send_record_id": record.id, "duplicate": False}
