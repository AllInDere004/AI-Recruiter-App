from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.advanced import AdminAuditEvent, UserRole
from app.models.user import User
from app.services.auth_service import get_current_user


def require_admin(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> User:
    role = db.query(UserRole.id).filter(UserRole.user_id == user.id, UserRole.role == "admin",
        UserRole.revoked_at.is_(None)).first()
    if role is None:
        raise HTTPException(403, "Administrator access required.")
    return user


def audit(db: Session, actor_id: int, action: str, *, target_type=None, target_id=None, metadata=None, request_id=None):
    safe = {key: value for key, value in (metadata or {}).items()
            if key in {"status", "count", "category", "provider"} and isinstance(value, (str, int, float, bool, type(None)))}
    db.add(AdminAuditEvent(actor_user_id=actor_id, action=action, target_type=target_type,
        target_id=str(target_id)[:100] if target_id is not None else None,
        metadata_json=safe, request_id=str(request_id)[:100] if request_id else None))
