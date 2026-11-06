import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import main
from app.config import settings
from app.database import get_db
from app.ml.embeddings import EmbeddingError
from app.models.job import Job
from app.models.profile import Profile
from app.models.user import User
from app.services.auth_service import create_access_token
from app.services.job_analyzer import analyze_job_description
from app.services.llm_client import LLMResponseError


ANALYSIS = {"title": "Backend Engineer", "company": "Example Inc", "required_skills": ["Python", "Docker"], "key_responsibilities": ["Build APIs"]}


class JobAnalyzerTests(unittest.TestCase):
    def test_prompt_and_json_validation(self):
        data = {**ANALYSIS, "required_skills": [" Python ", "python", "Docker", " "]}
        with patch("app.services.job_analyzer.call_llm", return_value=json.dumps(data)) as llm:
            result = analyze_job_description("Build Python services at Example Inc")
            self.assertEqual(result["required_skills"], ["Python", "Docker"])
            self.assertIn("Build Python services at Example Inc", llm.call_args.args[0])
            self.assertTrue(llm.call_args.kwargs["json_mode"])
        for response in ['{"required_skills": "Python"}', 'not json', '[]']:
            with patch("app.services.job_analyzer.call_llm", return_value=response):
                with self.assertRaises(LLMResponseError):
                    analyze_job_description("Description")
        with self.assertRaises(ValueError):
            analyze_job_description(" ")


class JobsAndMatchingAPITests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        self.engine_patch = patch.object(main, "engine", self.engine)
        self.engine_patch.start()
        self.key_patch = patch.object(settings, "LLM_API_KEY", "test-key")
        self.key_patch.start()
        self.gemini_patch = patch("app.services.llm_client.genai.Client")
        self.gemini = self.gemini_patch.start().return_value.__enter__.return_value
        self.gemini.models.generate_content.return_value = SimpleNamespace(text=json.dumps(ANALYSIS))

        def test_db():
            with Session(self.engine) as db:
                yield db

        self.overrides = main.app.dependency_overrides.copy()
        main.app.dependency_overrides[get_db] = test_db
        self.context = TestClient(main.app)
        self.client = self.context.__enter__()
        with Session(self.engine) as db:
            first = User(email="first@example.com", hashed_password="test-hash")
            second = User(email="second@example.com", hashed_password="test-hash")
            db.add_all([first, second])
            db.commit()
            self.user_id, self.other_id = first.id, second.id
        self.headers = {"Authorization": f"Bearer {create_access_token({'sub': 'first@example.com'})}"}
        self.other_headers = {"Authorization": f"Bearer {create_access_token({'sub': 'second@example.com'})}"}

    def tearDown(self):
        self.context.__exit__(None, None, None)
        main.app.dependency_overrides.clear()
        main.app.dependency_overrides.update(self.overrides)
        self.gemini_patch.stop()
        self.key_patch.stop()
        self.engine_patch.stop()
        self.engine.dispose()

    def analyze(self, headers=None, **fields):
        return self.client.post("/api/jobs/analyze", headers=headers or self.headers,
                                json={"description": "Build Python APIs with Docker.", **fields})

    def profile(self, parsed_data=None, raw_text="Experienced Python developer"):
        with Session(self.engine) as db:
            db.add(Profile(user_id=self.user_id, raw_resume_text=raw_text, parsed_data=parsed_data or {"skills": ["Python"]}))
            db.commit()

    def compare(self, job_id, headers=None):
        return self.client.post("/api/match/compare", headers=headers or self.headers, json={"job_id": job_id})

    def test_analysis_saves_gemini_output_and_job_response(self):
        response = self.analyze()
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["title"], ANALYSIS["title"])
        self.assertEqual(data["company"], ANALYSIS["company"])
        self.assertEqual(data["user_id"], self.user_id)
        self.assertEqual(data["extracted_skills"], ANALYSIS)
        self.assertIsNotNone(data["created_at"])
        with Session(self.engine) as db:
            job = db.query(Job).one()
            self.assertEqual(job.extracted_skills, ANALYSIS)
            self.assertEqual(job.description, "Build Python APIs with Docker.")

    def test_explicit_title_and_company_take_priority(self):
        response = self.analyze(title="My Title", company="My Company")
        self.assertEqual(response.json()["title"], "My Title")
        self.assertEqual(response.json()["company"], "My Company")

    def test_lists_only_owned_jobs_newest_first(self):
        first = self.analyze().json()
        second = self.analyze(title="Newer").json()
        self.analyze(headers=self.other_headers)
        response = self.client.get("/api/jobs/", headers=self.headers)
        self.assertEqual([job["id"] for job in response.json()], [second["id"], first["id"]])
        self.assertEqual(len(self.client.get("/api/jobs/", headers=self.other_headers).json()), 1)

    def test_analysis_errors_do_not_save_jobs(self):
        for text in ["invalid JSON", '{"required_skills": "Python"}']:
            self.gemini.models.generate_content.return_value = SimpleNamespace(text=text)
            self.assertEqual(self.analyze().status_code, 502)
        with patch.object(settings, "LLM_API_KEY", "dev_llm_key"):
            self.assertEqual(self.analyze().status_code, 503)
        self.assertEqual(self.analyze(description=" ").status_code, 422)
        with Session(self.engine) as db:
            self.assertEqual(db.query(Job).count(), 0)

    def test_compare_combines_semantics_and_skill_overlap(self):
        job = self.analyze().json()
        self.profile()
        with patch("app.api.match.get_embedding", side_effect=[[1.0, 0.0], [0.8, 0.6]]) as encode:
            response = self.compare(job["id"])
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["overall_score"], 71.0)
        self.assertEqual(response.json()["matched_skills"], ["Python"])
        self.assertEqual(response.json()["missing_skills"], ["Docker"])
        self.assertIn("80.0%", response.json()["summary"])
        self.assertEqual(encode.call_args_list[0].args[0], "Experienced Python developer")
        self.assertEqual(encode.call_args_list[1].args[0], job["description"])

    def test_no_required_skills_uses_semantics_only(self):
        self.gemini.models.generate_content.return_value = SimpleNamespace(text=json.dumps({**ANALYSIS, "required_skills": []}))
        job = self.analyze().json()
        self.profile()
        with patch("app.api.match.get_embedding", side_effect=[[1, 0], [0.8, 0.6]]):
            response = self.compare(job["id"])
        self.assertEqual(response.json()["overall_score"], 80.0)
        self.assertEqual(response.json()["matched_skills"], [])
        self.assertIn("semantic similarity only", response.json()["summary"])

    def test_scores_stay_in_zero_to_hundred_range(self):
        job = self.analyze().json()
        self.profile(parsed_data={"skills": ["Python", "Docker"]})
        with patch("app.api.match.get_embedding", side_effect=[[1, 0], [1, 0]]):
            self.assertEqual(self.compare(job["id"]).json()["overall_score"], 100)
        with patch("app.api.match.get_embedding", side_effect=[[1, 0], [-1, 0]]):
            self.assertEqual(self.compare(job["id"]).json()["overall_score"], 30)

    def test_missing_and_other_user_jobs_are_404_before_embedding(self):
        owned = self.analyze().json()
        with patch("app.api.match.get_embedding") as encode:
            self.assertEqual(self.compare(owned["id"], headers=self.other_headers).status_code, 404)
            self.assertEqual(self.compare(99999).status_code, 404)
            encode.assert_not_called()
        self.assertEqual(self.compare(owned["id"]).status_code, 404)

    def test_model_unavailable_and_invalid_vectors_return_503(self):
        job = self.analyze().json()
        self.profile()
        with patch("app.api.match.get_embedding", side_effect=EmbeddingError("Model could not load")):
            self.assertEqual(self.compare(job["id"]).status_code, 503)
        with patch("app.api.match.get_embedding", side_effect=[[1], [1, 2]]):
            self.assertEqual(self.compare(job["id"]).status_code, 503)

    def test_malformed_profile_skills_and_empty_text_are_rejected(self):
        job = self.analyze().json()
        self.profile(parsed_data={"skills": "Python"})
        with patch("app.api.match.get_embedding") as encode:
            self.assertEqual(self.compare(job["id"]).status_code, 422)
            encode.assert_not_called()
        with Session(self.engine) as db:
            profile = db.query(Profile).one()
            profile.parsed_data = {"skills": []}
            profile.raw_resume_text = " "
            db.commit()
        self.assertEqual(self.compare(job["id"]).status_code, 422)
        self.assertEqual(self.compare(0).status_code, 422)

    def test_all_job_and_matching_routes_require_authentication(self):
        self.assertEqual(self.client.post("/api/jobs/analyze", json={"description": "Python"}).status_code, 401)
        self.assertEqual(self.client.get("/api/jobs/").status_code, 401)
        self.assertEqual(self.client.post("/api/match/compare", json={"job_id": 1}).status_code, 401)
