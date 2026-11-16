from datetime import datetime, timezone
import hashlib
import re

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
from app.services.resume_parser import MAX_PDF_BYTES, PDFExtractionError, PDFTooLargeError, extract_text_from_pdf
from app.services.career_repository import optional_snapshot, preserve_original
from app.services.ai_usage import enforce_ai_usage


router = APIRouter(prefix="/api/resume", tags=["Resume"])


def _save_profile(db: Session, user_id: int, text: str, parsed: dict, metadata=None) -> Profile:
    preserve_original(db, user_id)
    profile = db.query(Profile).filter(Profile.user_id == user_id).first()
    if profile is None:
        profile = Profile(user_id=user_id, raw_resume_text=text)
        db.add(profile)
    profile.full_name = parsed.get("full_name")
    profile.raw_resume_text = text
    profile.parsed_data = parsed
    profile.updated_at = datetime.now(timezone.utc)
    try:
        # SessionLocal deliberately disables autoflush. Persist the new/updated
        # profile identity before Phase 2 snapshots query it in this transaction.
        db.flush()
        optional_snapshot(db, user_id, approved=False, metadata=metadata)
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
            # Retain provenance, never the uploaded PDF or its original local path.
            content = await file.read(MAX_PDF_BYTES + 1)
            if len(content) > MAX_PDF_BYTES:
                del content
                raise PDFTooLargeError("PDF must be 10 MB or smaller.")
            filename = re.sub(r"[\x00-\x1f\x7f]", "", (file.filename or "resume.pdf").replace("\\", "/").rsplit("/", 1)[-1])[:255]
            metadata = {"filename": filename or "resume.pdf", "content_type": "application/pdf",
                        "size_bytes": len(content), "sha256": hashlib.sha256(content).hexdigest(),
                        "page_count": None, "layout_available": False}
            del content
            await file.seek(0)
            raw_text = await extract_text_from_pdf(file)
            enforce_ai_usage(db, current_user.id)
            parsed = await run_in_threadpool(extract_profile_from_text, raw_text)
        except PDFTooLargeError as error:
            raise HTTPException(status_code=413, detail=str(error)) from None
        except PDFExtractionError as error:
            raise HTTPException(status_code=422, detail=str(error)) from None
        except LLMConfigurationError as error:
            raise HTTPException(status_code=503, detail=str(error)) from None
        except LLMError as error:
            raise HTTPException(status_code=502, detail=str(error)) from None
        return await run_in_threadpool(_save_profile, db, current_user.id, raw_text, parsed, metadata)
    finally:
        await file.close()
