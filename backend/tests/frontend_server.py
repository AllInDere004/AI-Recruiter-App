"""Local browser-test server: real FastAPI/SQLAlchemy/PDF/model path, fake Gemini only."""
import json
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path
from tempfile import TemporaryDirectory

import uvicorn
from sqlalchemy import create_engine

from app import main
from app.config import settings


def generate_content(**kwargs):
    system = kwargs["config"].system_instruction or ""
    if system.startswith("You extract factual profile"):
        data = {"full_name":"Frontend Test","email":"candidate@example.com","phone":None,"summary":"Python developer", "skills":["Python","SQL"],"experience":[],"education":[]}
    elif system.startswith("Extract only facts explicitly"):
        data = {"title":"Backend Engineer","company":"Integration Labs","required_skills":["Python","SQL","Docker"],"key_responsibilities":["Build APIs"]}
    elif system.startswith("You review factual grounding"):
        data = {"warnings":["Review candidate availability before sending."]}
    else:
        data = {"subject_line":"Application: Backend Engineer","body":"Hi Integration Labs,\n\nI build Python APIs and use SQL. I would welcome the opportunity to discuss the Backend Engineer role.\n\nRegards,\nFrontend Test"}
    return SimpleNamespace(text=json.dumps(data))


def run():
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
    with patch.object(settings,"LLM_API_KEY","browser-test-key"), patch("app.services.llm_client.genai.Client") as factory:
        factory.return_value.__enter__.return_value.models.generate_content.side_effect = generate_content
        try:
            uvicorn.run(main.app,host="127.0.0.1",port=8002)
        finally:
            engine.dispose()
            temporary.cleanup()


if __name__ == "__main__":
    run()
