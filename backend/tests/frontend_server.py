"""Local browser-test server: real FastAPI/SQLAlchemy/PDF/model path, fake Gemini only."""
import json
import os
from contextlib import ExitStack
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path
from tempfile import TemporaryDirectory

import uvicorn
from sqlalchemy import create_engine

from app import main
from app.config import settings
from app.providers.base import NormalizedJob, SearchPage


class BrowserJobProvider:
    name = "himalayas"
    configured = True

    def search(self, **kwargs):
        job = NormalizedJob(provider="himalayas", provider_job_id="browser-himalayas-1",
            title="Backend Engineer", company="Integration Labs", location="Pune, India",
            job_type="Full-time", salary_text="Salary not disclosed", experience_text="2+ years",
            skills=["Python", "SQL", "Docker"], description="Build Python APIs with SQL and Docker.",
            published_at=datetime.now(timezone.utc), provider_url="https://example.com/jobs/backend-engineer",
            application_url="https://example.com/jobs/backend-engineer", normalized={"source": "Himalayas"})
        return SearchPage([job], 1, kwargs.get("page", 1), kwargs.get("page_size", 20), "himalayas")


def generate_content(**kwargs):
    system = kwargs["config"].system_instruction or ""
    if system.startswith("You select source evidence"):
        payload = json.loads(kwargs["contents"].rsplit("\n", 1)[-1])
        data = {"evidence_ids": [str(item["id"]) for item in payload["verified_evidence"]][:60]}
    elif system.startswith("Offer concise learning guidance"):
        data = {"explanation": "Practice the missing requirement in a small project before claiming it on a resume."}
    elif system.startswith("You extract factual profile"):
        data = {"full_name":"Frontend Test","email":"candidate@example.com","phone":None,"summary":"Python developer", "skills":["Python","SQL"],"experience":[],"education":[]}
    elif system.startswith("Extract only facts explicitly"):
        data = {"title":"Backend Engineer","company":"Integration Labs","required_skills":["Python","SQL","Docker"],"key_responsibilities":["Build APIs"]}
    elif system.startswith("You review factual grounding"):
        data = {"warnings":["Review candidate availability before sending."]}
    elif system.startswith("You create interview-practice questions") or system.startswith("Create one concise interview follow-up"):
        payload = json.loads(kwargs["contents"])
        interview_type = payload["interview_type"]
        data = {"questions": [{
            "question": f"Explain one concrete example that demonstrates your {interview_type} interview skills.",
            "question_type": interview_type,
            "competency": "evidence-based communication",
            "rubric": {"relevance": "Answers the question directly.", "evidence": "Uses a concrete example."},
        } for _ in range(payload.get("question_count", 1))]}
        for index, item in enumerate(data["questions"], 1):
            item["question"] = f"{item['question']} Focus area {index}."
    elif system.startswith("Evaluate interview-practice answers"):
        payload = json.loads(kwargs["contents"])
        data = {"feedback": []}
        for row in payload["untrusted_responses"]:
            answer = row["answer"]
            data["feedback"].append({
                "question_id": row["question_id"],
                "categories": [{"category": category, "score": 80, "rationale": "The answer provides a relevant practice example."} for category in payload["rubric"]],
                "evidence_quotes": [answer[:80]],
                "strengths": ["Uses a concrete example."],
                "improvements": ["Add a measurable result."],
                "sample_improved_answer": "One possible improvement is to add the decision, action, and measurable outcome.",
            })
    else:
        data = {"subject_line":"Application: Backend Engineer","body":"Hi Integration Labs,\n\nI build Python APIs and use SQL. I would welcome the opportunity to discuss the Backend Engineer role.\n\nRegards,\nFrontend Test"}
    return SimpleNamespace(text=json.dumps(data))


def run():
    settings.ENABLE_CAREER_INTELLIGENCE = os.environ.get("TEST_CAREER_INTELLIGENCE") == "1"
    settings.ENABLE_JOB_DISCOVERY = os.environ.get("TEST_JOB_DISCOVERY") == "1"
    settings.ENABLE_ADVANCED_FEATURES = os.environ.get("TEST_ADVANCED_FEATURES") == "1"
    temporary = TemporaryDirectory(prefix="frontend-fastapi-test-")
    engine = create_engine(f"sqlite:///{Path(temporary.name) / 'frontend.sqlite'}",connect_args={"check_same_thread":False,"timeout":30})
    with engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA journal_mode=WAL")
    main.engine = engine
    # Use an isolated dependency for every real HTTP request.
    from sqlalchemy.orm import Session
    from app.database import get_db
    def db_session():
        with Session(engine) as session:
            yield session
    main.app.dependency_overrides[get_db] = db_session
    for middleware in main.app.user_middleware:
        if middleware.cls.__name__ == "CORSMiddleware":
            middleware.kwargs["allow_origins"] = ["http://localhost:3001","http://127.0.0.1:3001"]
    with ExitStack() as stack:
        stack.enter_context(patch.object(settings,"LLM_API_KEY","browser-test-key"))
        stack.enter_context(patch.object(settings,"HIMALAYAS_API_KEY","browser-test-provider-key"))
        stack.enter_context(patch.object(settings,"JOOBLE_API_KEY","browser-test-provider-key"))
        stack.enter_context(patch("app.api.discovery._provider",return_value=BrowserJobProvider()))
        # Keep browser regression hermetic. The embedding implementation and its
        # error handling have dedicated unit tests; UI/API flow must not depend on
        # a model download or a workstation cache.
        stack.enter_context(patch("app.api.match.get_embedding",return_value=[1.0, 0.5, 0.25]))
        stack.enter_context(patch("app.ml.scorer.get_embedding",return_value=[1.0, 0.5, 0.25]))
        factory = stack.enter_context(patch("app.services.llm_client.genai.Client"))
        factory.return_value.__enter__.return_value.models.generate_content.side_effect = generate_content
        try:
            uvicorn.run(main.app,host="127.0.0.1",port=8002)
        finally:
            engine.dispose()
            temporary.cleanup()


if __name__ == "__main__":
    run()
