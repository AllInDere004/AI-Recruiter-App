from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.draft import Draft
from app.models.user import User
from app.schemas.email import DraftResponse, DraftUpdate
from app.services.auth_service import get_current_user


router = APIRouter(prefix="/api/drafts", tags=["Drafts & Tracker"])


def _owned_draft(db: Session, user_id: int, draft_id: int) -> Draft:
    draft = db.query(Draft).filter(Draft.id == draft_id, Draft.user_id == user_id).first()
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found.")
    return draft


@router.get("/", response_model=List[DraftResponse])
def list_drafts(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Draft).filter(Draft.user_id == current_user.id).order_by(Draft.created_at.desc(), Draft.id.desc()).all()


@router.get("/{draft_id}", response_model=DraftResponse)
def get_draft(draft_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return _owned_draft(db, current_user.id, draft_id)


@router.put("/{draft_id}", response_model=DraftResponse)
def update_draft(draft_id: int, update: DraftUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    draft = _owned_draft(db, current_user.id, draft_id)
    changes = update.model_dump(exclude_unset=True)
    if "body" in changes and changes["body"] != draft.body:
        # The original generated-text score no longer describes the edited email.
        draft.match_score = None
    for field, value in changes.items():
        setattr(draft, field, value)
    draft.updated_at = datetime.now(timezone.utc)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(draft)
    return draft


@router.delete("/{draft_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_draft(draft_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    draft = _owned_draft(db, current_user.id, draft_id)
    db.delete(draft)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    return Response(status_code=status.HTTP_204_NO_CONTENT)
