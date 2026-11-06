from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.ml.embeddings import EmbeddingError
from app.ml.scorer import score_draft
from app.models.draft import Draft
from app.models.job import Job
from app.models.profile import Profile
from app.models.user import User
from app.schemas.email import EmailGenerateRequest, EmailGenerateResponse
from app.services.auth_service import get_current_user
from app.services.email_generator import generate_email
from app.services.hallucination_check import verify_email_facts
from app.services.llm_client import LLMConfigurationError, LLMError


router = APIRouter(prefix="/api/email", tags=["Email"])


@router.post("/generate", response_model=EmailGenerateResponse)
def generate(req: EmailGenerateRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    job = db.query(Job).filter(Job.id == req.job_id, Job.user_id == current_user.id).first()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found. Upload a resume before generating email.")
    if not profile.raw_resume_text.strip() or not job.description.strip():
        raise HTTPException(status_code=422, detail="Resume text and job description cannot be blank.")
    try:
        email = generate_email(profile.raw_resume_text, job.description, req.situation, req.tone, req.custom_notes or "")
        warnings = verify_email_facts(profile.raw_resume_text, email["subject_line"] + "\n" + email["body"])
        score = score_draft(profile.raw_resume_text, job.description, email["body"])
    except LLMConfigurationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from None
    except LLMError as error:
        raise HTTPException(status_code=502, detail=str(error)) from None
    except EmbeddingError as error:
        raise HTTPException(status_code=503, detail=str(error)) from None
    except ValueError:
        raise HTTPException(status_code=503, detail="The semantic model could not score this email.") from None
    draft = Draft(
        user_id=current_user.id, job_id=job.id, situation=req.situation, tone=req.tone,
        subject_line=email["subject_line"], body=email["body"], match_score=score,
    )
    db.add(draft)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(draft)
    return EmailGenerateResponse(
        draft_id=draft.id, subject_line=draft.subject_line, body=draft.body,
        match_score=draft.match_score, hallucination_warnings=warnings,
    )
