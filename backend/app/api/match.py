from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.ml.embeddings import EmbeddingError, get_embedding
from app.ml.matcher import calculate_skill_overlap, cosine_similarity
from app.models.job import Job
from app.models.profile import Profile
from app.models.user import User
from app.schemas.job import MatchRequest, MatchResponse
from app.services.auth_service import get_current_user


router = APIRouter(prefix="/api/match", tags=["Matching"])


def _skill_list(data, label: str):
    if data is None:
        return []
    key = "skills" if label == "Profile" else "required_skills"
    values = data.get(key, []) if isinstance(data, dict) else None
    if not isinstance(values, list) or not all(isinstance(skill, str) for skill in values):
        raise HTTPException(status_code=422, detail=f"{label} skills must be an array of strings.")
    return values


@router.post("/compare", response_model=MatchResponse)
def compare_job(match_in: MatchRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    job = db.query(Job).filter(Job.id == match_in.job_id, Job.user_id == current_user.id).first()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found. Upload a resume before comparing jobs.")
    if not profile.raw_resume_text.strip() or not job.description.strip():
        raise HTTPException(status_code=422, detail="Both resume text and job description must be nonempty.")

    overlap = calculate_skill_overlap(_skill_list(profile.parsed_data, "Profile"), _skill_list(job.extracted_skills, "Job"))
    try:
        resume_vector = get_embedding(profile.raw_resume_text)
        job_vector = get_embedding(job.description)
        semantic_score = max(0.0, cosine_similarity(resume_vector, job_vector)) * 100
    except EmbeddingError as error:
        raise HTTPException(status_code=503, detail=str(error)) from None
    except ValueError:
        raise HTTPException(status_code=503, detail="The semantic model returned incompatible embedding vectors.") from None
    required_count = len(overlap["matched_skills"]) + len(overlap["missing_skills"])
    overall = 0.7 * semantic_score + 0.3 * overlap["overlap_percentage"] if required_count else semantic_score
    summary = (
        f"Semantic similarity: {semantic_score:.1f}%. "
        f"Matched {len(overlap['matched_skills'])} of {required_count} required skills "
        f"({overlap['overlap_percentage']:.1f}% coverage). "
        + ("Overall score weights semantic similarity 70% and skill coverage 30%."
           if required_count else "No required skills were listed; the overall score uses semantic similarity only.")
    )
    return MatchResponse(
        overall_score=round(max(0.0, min(100.0, overall)), 2),
        matched_skills=overlap["matched_skills"],
        missing_skills=overlap["missing_skills"],
        summary=summary,
    )
