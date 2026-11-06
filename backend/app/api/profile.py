from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.profile import Profile
from app.models.user import User
from app.schemas.profile import ProfileResponse, ProfileUpdate
from app.services.auth_service import get_current_user


router = APIRouter(prefix="/api/profile", tags=["Profile"])


def _get_profile(db: Session, user_id: int) -> Profile:
    profile = db.query(Profile).filter(Profile.user_id == user_id).first()
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found. Upload a resume first.")
    return profile


@router.get("/me", response_model=ProfileResponse)
def get_profile(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return _get_profile(db, current_user.id)


@router.put("/me", response_model=ProfileResponse)
def update_profile(
    update: ProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = _get_profile(db, current_user.id)
    for field, value in update.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)
    profile.updated_at = datetime.now(timezone.utc)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(profile)
    return profile
