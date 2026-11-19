from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import distinct, func, inspect
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import settings
from app.models.advanced import InterviewEvaluation, InterviewSession
from app.models.discovery import Application, ApplicationEvent, ExternalJobListing, SavedJob
from app.models.user import User
from app.services.auth_service import get_current_user
from app.services.discovery_repository import require_ready


router = APIRouter(prefix="/api/analytics", tags=["Career analytics"])


@router.get("/career")
def career(date_from: datetime | None = None, date_to: datetime | None = None,
           company: str | None = Query(default=None, max_length=200),
           job_type: str | None = Query(default=None, max_length=100),
           stage: str | None = Query(default=None, max_length=30),
           db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_ready(db)
    query = db.query(Application).join(SavedJob, SavedJob.id == Application.saved_job_id).join(
        ExternalJobListing, ExternalJobListing.id == SavedJob.listing_id).filter(Application.user_id == user.id)
    if date_from: query = query.filter(Application.created_at >= date_from)
    if date_to: query = query.filter(Application.created_at < date_to)
    if company: query = query.filter(ExternalJobListing.company.ilike(f"%{company}%"))
    if job_type: query = query.filter(ExternalJobListing.job_type == job_type)
    if stage: query = query.filter(Application.status == stage)
    ids = [row[0] for row in query.with_entities(Application.id).all()]
    total = len(ids)
    submitted_ids = [row[0] for row in query.with_entities(Application.id).filter(Application.submitted_at.is_not(None)).all()]
    def reached(states):
        if not submitted_ids: return 0
        return db.query(func.count(distinct(ApplicationEvent.application_id))).filter(
            ApplicationEvent.user_id == user.id, ApplicationEvent.application_id.in_(submitted_ids),
            ApplicationEvent.to_status.in_(states)).scalar() or 0
    responses, interviews, offers, rejections = reached(["Assessment","Interview","Offer","Rejected"]), reached(["Interview"]), reached(["Offer"]), reached(["Rejected"])
    states = {name: count for name, count in query.with_entities(Application.status, func.count(Application.id)).group_by(Application.status).all()}
    weekly_rows = query.with_entities(func.date(Application.created_at), func.count(Application.id)).group_by(
        func.date(Application.created_at)).order_by(func.date(Application.created_at)).all()
    session_ids, evaluation_scores, practice_by_type = [], [], {}
    tables = set(inspect(db.connection()).get_table_names())
    if settings.ENABLE_ADVANCED_FEATURES and {"interview_sessions", "interview_evaluations"} <= tables:
        sessions = db.query(InterviewSession).filter(InterviewSession.user_id == user.id)
        if date_from: sessions = sessions.filter(InterviewSession.created_at >= date_from)
        if date_to: sessions = sessions.filter(InterviewSession.created_at < date_to)
        session_ids = [row[0] for row in sessions.with_entities(InterviewSession.id).all()]
        evaluation_scores = [row[0] for row in db.query(InterviewEvaluation.practice_score).filter(
            InterviewEvaluation.user_id == user.id,
            InterviewEvaluation.session_id.in_(session_ids or [-1])).all()]
        practice_by_type = {kind: round(score, 1) for kind, score in db.query(
            InterviewSession.interview_type, func.avg(InterviewEvaluation.practice_score)).join(
            InterviewEvaluation, InterviewEvaluation.session_id == InterviewSession.id).filter(
            InterviewSession.user_id == user.id,
            InterviewSession.id.in_(session_ids or [-1])).group_by(InterviewSession.interview_type).all()}
    submitted = len(submitted_ids)
    return {"filters": {"date_from": date_from, "date_to": date_to, "company": company, "job_type": job_type, "stage": stage},
        "funnel": {"saved": total, "submitted": submitted, "responses": responses, "interviews": interviews,
            "offers": offers, "rejections": rejections, "state_counts": states},
        "rates": {"response": round(responses*100/submitted,1) if submitted else None,
            "interview": round(interviews*100/submitted,1) if submitted else None,
            "offer": round(offers*100/submitted,1) if submitted else None},
        "weekly_applications": [{"date": str(day), "applications": count} for day, count in weekly_rows],
        "interview_practice": {"sessions": len(session_ids),
            "average_score": round(sum(evaluation_scores)/len(evaluation_scores),1) if evaluation_scores else None,
            "average_by_type": practice_by_type},
        "definitions": {"submitted": "Applications with explicit submission confirmation in the selected application range.",
            "conversion": "Each submitted application is counted once when it first reaches a qualifying stage.",
            "practice": "AI practice estimates from saved interview evaluations; not hiring predictions."}}
