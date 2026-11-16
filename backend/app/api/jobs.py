from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.job import Job
from app.models.user import User
from app.schemas.job import JobCreate, JobResponse
from app.services.auth_service import get_current_user
from app.services.job_analyzer import analyze_job_description
from app.services.llm_client import LLMConfigurationError, LLMError
from app.services.ai_usage import enforce_ai_usage


router = APIRouter(prefix="/api/jobs", tags=["Jobs"])


@router.post("/analyze", response_model=JobResponse)
def analyze_job(job_in: JobCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    enforce_ai_usage(db, current_user.id)
    try:
        analysis = analyze_job_description(job_in.description)
    except LLMConfigurationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from None
    except LLMError as error:
        raise HTTPException(status_code=502, detail=str(error)) from None
    job = Job(
        user_id=current_user.id,
        title=job_in.title if job_in.title is not None else analysis["title"],
        company=job_in.company if job_in.company is not None else analysis["company"],
        description=job_in.description,
        extracted_skills=analysis,
    )
    db.add(job)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(job)
    return job


@router.get("/", response_model=List[JobResponse])
def list_jobs(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Job).filter(Job.user_id == current_user.id).order_by(Job.created_at.desc(), Job.id.desc()).all()
