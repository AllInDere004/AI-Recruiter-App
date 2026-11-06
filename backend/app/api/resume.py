from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.database import get_db
from app.models.profile import Profile
from app.models.user import User
from app.schemas.profile import ProfileResponse
from app.services.auth_service import get_current_user
from app.services.llm_client import LLMConfigurationError, LLMError
from app.services.profile_extractor import extract_profile_from_text
from app.services.resume_parser import PDFExtractionError, PDFTooLargeError, extract_text_from_pdf


router = APIRouter(prefix="/api/resume", tags=["Resume"])


def _save_profile(db: Session, user_id: int, text: str, parsed: dict) -> Profile:
    profile = db.query(Profile).filter(Profile.user_id == user_id).first()
    if profile is None:
        profile = Profile(user_id=user_id, raw_resume_text=text)
        db.add(profile)
    profile.full_name = parsed.get("full_name")
    profile.raw_resume_text = text
    profile.parsed_data = parsed
    profile.updated_at = datetime.now(timezone.utc)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Your profile changed concurrently. Please retry the upload.") from None
    db.refresh(profile)
    return profile


@router.post("/upload", response_model=ProfileResponse)
async def upload_resume(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        if (file.content_type or "").split(";", 1)[0].strip().lower() != "application/pdf":
            raise HTTPException(status_code=415, detail="Only PDF resumes are supported (application/pdf).")
        try:
            raw_text = await extract_text_from_pdf(file)
            parsed = await run_in_threadpool(extract_profile_from_text, raw_text)
        except PDFTooLargeError as error:
            raise HTTPException(status_code=413, detail=str(error)) from None
        except PDFExtractionError as error:
            raise HTTPException(status_code=422, detail=str(error)) from None
        except LLMConfigurationError as error:
            raise HTTPException(status_code=503, detail=str(error)) from None
        except LLMError as error:
            raise HTTPException(status_code=502, detail=str(error)) from None
        return await run_in_threadpool(_save_profile, db, current_user.id, raw_text, parsed)
    finally:
        await file.close()
