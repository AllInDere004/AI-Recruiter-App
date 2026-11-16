"""Owner-scoped text interview practice and AI feedback."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.advanced import InterviewAnswer, InterviewEvaluation, InterviewQuestion, InterviewSession
from app.models.user import User
from app.schemas.interviews import AnswerSubmit, InterviewStart, InterviewStateUpdate
from app.services.ai_usage import enforce_ai_usage
from app.services.auth_service import get_current_user
from app.services.interview_engine import (
    FEEDBACK_PROMPT_VERSION, QUESTION_PROMPT_VERSION, RUBRIC_VERSIONS,
    evaluate_answers, generate_follow_up, generate_questions, owned_job, owned_resume,
    owned_session, require_ready, schema_ready, set_session_state,
)
from app.services.llm_client import LLMConfigurationError, LLMError


router = APIRouter(prefix="/api/interviews", tags=["Interview practice"])


def _question(value, answer=None, evaluation=None):
    return {
        "id": value.id, "position": value.position, "question_type": value.question_type,
        "question": value.question_text, "competency": value.competency,
        "rubric": value.rubric_json, "follow_up_to_id": value.follow_up_to_id,
        "answer": None if answer is None else {"id": answer.id, "text": answer.answer_text,
            "version": answer.version, "submitted_at": answer.submitted_at},
        "evaluation": None if evaluation is None else {
            "id": evaluation.id, "categories": evaluation.scores_json,
            "evidence": evaluation.evidence_json, "strengths": evaluation.strengths_json,
            "improvements": evaluation.improvements_json, "sample_improved_answer": evaluation.sample_answer,
            "practice_score": evaluation.practice_score, "rubric_version": evaluation.rubric_version,
            "model": evaluation.model, "created_at": evaluation.created_at,
        },
    }


def _session(db, value, *, details=False):
    payload = {
        "id": value.id, "job_id": value.job_id, "resume_version_id": value.resume_version_id,
        "interview_type": value.interview_type, "difficulty": value.difficulty,
        "status": value.status, "question_count": value.question_count,
        "time_limit_minutes": value.time_limit_minutes, "version": value.version,
        "started_at": value.started_at, "paused_at": value.paused_at,
        "completed_at": value.completed_at, "evaluated_at": value.evaluated_at,
        "created_at": value.created_at,
        "disclaimer": "AI scores are practice estimates, not hiring predictions.",
    }
    if details:
        questions = db.query(InterviewQuestion).filter(
            InterviewQuestion.session_id == value.id, InterviewQuestion.user_id == value.user_id,
        ).order_by(InterviewQuestion.position).all()
        answers = {row.question_id: row for row in db.query(InterviewAnswer).filter(
            InterviewAnswer.session_id == value.id, InterviewAnswer.user_id == value.user_id).all()}
        evaluations = {row.question_id: row for row in db.query(InterviewEvaluation).filter(
            InterviewEvaluation.session_id == value.id, InterviewEvaluation.user_id == value.user_id).all()}
        payload["questions"] = [_question(row, answers.get(row.id), evaluations.get(row.id)) for row in questions]
    return payload


def _commit(db):
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise


@router.get("/status")
def status(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return {"enabled": settings.ENABLE_ADVANCED_FEATURES, "ready": settings.ENABLE_ADVANCED_FEATURES and schema_ready(db),
            "text_only": True, "gmail_enabled": False}


@router.post("/sessions", status_code=201)
def start(payload: InterviewStart, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_ready(db)
    resume = owned_resume(db, user.id, payload.resume_version_id)
    job = owned_job(db, user.id, payload.job_id)
    enforce_ai_usage(db, user.id)
    try:
        generated, context_hash = generate_questions(
            resume, job, payload.interview_type, payload.difficulty, payload.question_count,
        )
    except LLMConfigurationError as error:
        raise HTTPException(503, str(error)) from None
    except LLMError as error:
        raise HTTPException(502, str(error)) from None
    session = InterviewSession(
        user_id=user.id, job_id=job.id if job else None, resume_version_id=resume.id,
        interview_type=payload.interview_type, difficulty=payload.difficulty,
        question_count=payload.question_count, time_limit_minutes=payload.time_limit_minutes,
        prompt_version=QUESTION_PROMPT_VERSION, rubric_version=RUBRIC_VERSIONS[payload.interview_type],
        model=settings.LLM_MODEL, context_hash=context_hash,
    )
    db.add(session); db.flush()
    for position, item in enumerate(generated.questions, 1):
        db.add(InterviewQuestion(
            user_id=user.id, session_id=session.id, position=position,
            question_type=item.question_type, question_text=item.question.strip(),
            competency=item.competency.strip(), rubric_json=item.rubric,
        ))
    _commit(db); db.refresh(session)
    return _session(db, session, details=True)


@router.get("/sessions")
def history(page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=50),
            db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_ready(db)
    query = db.query(InterviewSession).filter(InterviewSession.user_id == user.id)
    total = query.count()
    values = query.order_by(InterviewSession.created_at.desc(), InterviewSession.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"sessions": [_session(db, value) for value in values], "total": total, "page": page, "page_size": page_size}


@router.get("/sessions/{session_id}")
def get_session(session_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_ready(db)
    return _session(db, owned_session(db, user.id, session_id), details=True)


@router.put("/sessions/{session_id}/state")
def update_state(session_id: int, payload: InterviewStateUpdate, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    require_ready(db)
    value = set_session_state(db, owned_session(db, user.id, session_id, lock=True), payload.action, payload.expected_version)
    _commit(db); db.refresh(value)
    return _session(db, value, details=True)


@router.put("/sessions/{session_id}/questions/{question_id}/answer")
def submit_answer(session_id: int, question_id: int, payload: AnswerSubmit,
                  db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_ready(db)
    session = owned_session(db, user.id, session_id, lock=True)
    if session.status not in {"in_progress", "paused", "completed"}:
        raise HTTPException(409, "This interview no longer accepts answers.")
    question = db.query(InterviewQuestion).filter(
        InterviewQuestion.id == question_id, InterviewQuestion.session_id == session.id,
        InterviewQuestion.user_id == user.id).first()
    if question is None:
        raise HTTPException(404, "Interview question not found.")
    answer = db.query(InterviewAnswer).filter(
        InterviewAnswer.question_id == question.id, InterviewAnswer.session_id == session.id,
        InterviewAnswer.user_id == user.id).first()
    if answer is None:
        answer = InterviewAnswer(user_id=user.id, session_id=session.id, question_id=question.id, answer_text=payload.answer)
        db.add(answer)
    else:
        answer.answer_text = payload.answer
        answer.version += 1
        answer.updated_at = datetime.now(timezone.utc)
        db.query(InterviewEvaluation).filter(InterviewEvaluation.answer_id == answer.id, InterviewEvaluation.user_id == user.id).delete()
        session.evaluated_at = None
    db.flush()
    answered = db.query(InterviewAnswer).filter(InterviewAnswer.session_id == session.id, InterviewAnswer.user_id == user.id).count()
    if answered >= session.question_count:
        session.status = "completed"
        session.completed_at = datetime.now(timezone.utc)
    session.version += 1
    _commit(db); db.refresh(session)
    return _session(db, session, details=True)


@router.post("/sessions/{session_id}/questions/{question_id}/follow-up", status_code=201)
def follow_up(session_id: int, question_id: int, db: Session = Depends(get_db),
              user: User = Depends(get_current_user)):
    require_ready(db)
    session = owned_session(db, user.id, session_id, lock=True)
    question = db.query(InterviewQuestion).filter(InterviewQuestion.id == question_id,
        InterviewQuestion.session_id == session.id, InterviewQuestion.user_id == user.id).first()
    answer = db.query(InterviewAnswer).filter(InterviewAnswer.question_id == question_id,
        InterviewAnswer.session_id == session.id, InterviewAnswer.user_id == user.id).first()
    if question is None or answer is None:
        raise HTTPException(409, "Submit an answer before requesting a follow-up.")
    if db.query(InterviewQuestion.id).filter(InterviewQuestion.follow_up_to_id == question.id,
            InterviewQuestion.user_id == user.id).first():
        raise HTTPException(409, "A follow-up already exists for this question.")
    enforce_ai_usage(db, user.id)
    try:
        generated = generate_follow_up(session, question, answer)
    except LLMConfigurationError as error:
        raise HTTPException(503, str(error)) from None
    except LLMError as error:
        raise HTTPException(502, str(error)) from None
    position = db.query(InterviewQuestion).filter(InterviewQuestion.session_id == session.id).count() + 1
    value = InterviewQuestion(user_id=user.id, session_id=session.id, position=position,
        question_type=generated.question_type, question_text=generated.question,
        competency=generated.competency, rubric_json=generated.rubric, follow_up_to_id=question.id)
    db.add(value); session.question_count += 1; session.status = "in_progress"; session.completed_at = None; session.version += 1
    _commit(db); db.refresh(value)
    return _question(value)


@router.post("/sessions/{session_id}/evaluate")
def evaluate(session_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    require_ready(db)
    session = owned_session(db, user.id, session_id, lock=True)
    questions = db.query(InterviewQuestion).filter(InterviewQuestion.session_id == session.id,
        InterviewQuestion.user_id == user.id).order_by(InterviewQuestion.position).all()
    answers = {row.question_id: row for row in db.query(InterviewAnswer).filter(
        InterviewAnswer.session_id == session.id, InterviewAnswer.user_id == user.id).all()}
    if len(answers) != len(questions):
        raise HTTPException(409, "Answer every interview question before requesting feedback.")
    existing = db.query(InterviewEvaluation).filter(InterviewEvaluation.session_id == session.id,
        InterviewEvaluation.user_id == user.id).count()
    if existing == len(questions) and session.status == "evaluated":
        return _session(db, session, details=True)
    enforce_ai_usage(db, user.id)
    try:
        feedback = evaluate_answers(session, [(q, answers[q.id]) for q in questions])
    except LLMConfigurationError as error:
        raise HTTPException(503, str(error)) from None
    except LLMError as error:
        raise HTTPException(502, str(error)) from None
    by_id = {item.question_id: item for item in feedback.feedback}
    db.query(InterviewEvaluation).filter(InterviewEvaluation.session_id == session.id,
        InterviewEvaluation.user_id == user.id).delete()
    for question in questions:
        item = by_id[question.id]
        score = round(sum(category.score for category in item.categories) / len(item.categories))
        db.add(InterviewEvaluation(user_id=user.id, session_id=session.id, question_id=question.id,
            answer_id=answers[question.id].id, rubric_version=session.rubric_version,
            prompt_version=FEEDBACK_PROMPT_VERSION, model=settings.LLM_MODEL,
            scores_json=[value.model_dump() for value in item.categories],
            evidence_json=item.evidence_quotes, strengths_json=item.strengths,
            improvements_json=item.improvements, sample_answer=item.sample_improved_answer,
            practice_score=score))
    session.status = "evaluated"; session.evaluated_at = datetime.now(timezone.utc); session.version += 1
    _commit(db); db.refresh(session)
    return _session(db, session, details=True)
