"""AI usage control never stores candidate input or credentials."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import main
from app.config import settings
from app.database import get_db
from app.models.job import Job
from app.models.profile import Profile
from app.models.user import User
from app.services.auth_service import create_access_token
from app.services import ai_usage
from test_resume_parser import make_pdf


class UsageBudgetTests(unittest.TestCase):
    def setUp(self):
        ai_usage._usage.clear()
        self.engine = object()
        self.db = SimpleNamespace(get_bind=lambda: self.engine)

    def tearDown(self):
        ai_usage._usage.clear()

    def test_budget_is_per_user_and_engine_and_returns_retry_after(self):
        with patch.object(settings,"AI_REQUESTS_PER_MINUTE",1),patch("app.services.ai_usage.monotonic",return_value=100):
            ai_usage.enforce_ai_usage(self.db,1)
            ai_usage.enforce_ai_usage(self.db,2)
            other_engine=object()
            ai_usage.enforce_ai_usage(SimpleNamespace(get_bind=lambda:other_engine),1)
            with self.assertRaises(HTTPException) as caught:
                ai_usage.enforce_ai_usage(self.db,1)
            self.assertEqual(caught.exception.status_code,429)
            self.assertEqual(caught.exception.headers["Retry-After"],"60")

    def test_expired_usage_allows_retry(self):
        with patch.object(settings,"AI_REQUESTS_PER_MINUTE",1):
            with patch("app.services.ai_usage.monotonic",return_value=100):
                ai_usage.enforce_ai_usage(self.db,1)
            with patch("app.services.ai_usage.monotonic",return_value=161):
                ai_usage.enforce_ai_usage(self.db,1)
            self.assertEqual(len(next(iter(ai_usage._usage.values()))),1)

    def test_storage_is_bounded_and_keys_contain_only_numeric_identity(self):
        with patch("app.services.ai_usage.MAX_TRACKED_USERS",3):
            for user_id in range(10):
                ai_usage.enforce_ai_usage(self.db,user_id)
        self.assertEqual(len(ai_usage._usage),3)
        self.assertTrue(all(len(key)==2 and all(type(part) is int for part in key) for key in ai_usage._usage))


class ExistingAIRouteBudgetTests(unittest.TestCase):
    def test_original_ai_routes_share_budget_after_validation_and_ownership_checks(self):
        engine=create_engine("sqlite://",connect_args={"check_same_thread":False},poolclass=StaticPool)
        original=main.app.dependency_overrides.copy()
        def test_db():
            with Session(engine) as db:
                yield db
        main.app.dependency_overrides[get_db]=test_db
        ai_usage._usage.clear()
        try:
            with patch.object(main,"engine",engine),patch.object(settings,"AI_REQUESTS_PER_MINUTE",1),TestClient(main.app) as client:
                with Session(engine) as db:
                    user=User(email="budget@example.com",hashed_password="unused")
                    db.add(user);db.flush()
                    db.add(Profile(user_id=user.id,raw_resume_text="Synthetic Python",parsed_data={"skills":["Python"]}))
                    job=Job(user_id=user.id,description="Python",extracted_skills={"required_skills":["Python"]})
                    db.add(job);db.commit();job_id=job.id
                headers={"Authorization":f"Bearer {create_access_token({'sub':'budget@example.com'})}"}
                # Invalid PDF is rejected before consuming any AI budget.
                invalid=client.post("/api/resume/upload",headers=headers,files={"file":("bad.pdf",b"invalid","application/pdf")})
                self.assertEqual(invalid.status_code,422)
                self.assertEqual(len(ai_usage._usage),0)
                with patch("app.api.jobs.analyze_job_description",return_value={"title":None,"company":None,"required_skills":[],"key_responsibilities":[]}):
                    first=client.post("/api/jobs/analyze",headers=headers,json={"description":"Python role"})
                self.assertEqual(first.status_code,200,first.text)
                with patch("app.api.resume.extract_profile_from_text") as parse,patch("app.api.email.generate_email") as generate:
                    resume=client.post("/api/resume/upload",headers=headers,files={"file":("resume.pdf",make_pdf("Synthetic Python"),"application/pdf")})
                    self.assertEqual(resume.status_code,429)
                    parse.assert_not_called()
                    email=client.post("/api/email/generate",headers=headers,json={"job_id":job_id,"situation":"apply","tone":"professional"})
                    self.assertEqual(email.status_code,429)
                    generate.assert_not_called()
                    missing=client.post("/api/email/generate",headers=headers,json={"job_id":999999,"situation":"apply","tone":"professional"})
                    self.assertEqual(missing.status_code,404)
                    self.assertIn("Retry-After",email.headers)
                repeated=client.post("/api/jobs/analyze",headers=headers,json={"description":"Python role"})
                self.assertEqual(repeated.status_code,429)
        finally:
            main.app.dependency_overrides.clear()
            main.app.dependency_overrides.update(original)
            ai_usage._usage.clear()
            engine.dispose()
