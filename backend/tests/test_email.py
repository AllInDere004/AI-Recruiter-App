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
from app.models.draft import Draft
from app.models.job import Job
from app.models.profile import Profile
from app.models.user import User
from app.services.auth_service import create_access_token
from app.services.email_generator import SITUATION_TEMPLATES, generate_email
from app.services.llm_client import LLMResponseError


EMAIL = {"subject_line": "Python engineering opportunity", "body": "I build Python APIs and use SQL. I would welcome an opportunity to contribute."}


class EmailGeneratorTests(unittest.TestCase):
    def test_all_situations_include_grounded_context_tone_and_notes(self):
        for situation in SITUATION_TEMPLATES:
            with self.subTest(situation=situation), patch("app.services.email_generator.call_llm", return_value=json.dumps(EMAIL)) as llm:
                self.assertEqual(generate_email("Candidate resume", "Target job", situation, "confident", "Please keep it brief"), EMAIL)
                prompt = llm.call_args.args[0]
                for value in ["Candidate resume", "Target job", "confident", "Please keep it brief", situation]:
                    self.assertIn(value, prompt)
                self.assertTrue(llm.call_args.kwargs["json_mode"])

    def test_missing_and_unknown_templates_use_safe_fallback(self):
        with patch("app.services.email_generator.call_llm", return_value=json.dumps(EMAIL)) as llm:
            with patch("pathlib.Path.read_text", side_effect=FileNotFoundError):
                self.assertEqual(generate_email("Resume", "Job", "apply", "professional"), EMAIL)
            self.assertIn("Write a recruiter email", llm.call_args.args[0])
            with patch("pathlib.Path.read_text") as read:
                generate_email("Resume", "Job", "../../config", "professional")
                read.assert_not_called()

    def test_invalid_generated_email_is_rejected(self):
        for response in ['{}', '{"subject_line": "Subject", "body": " "}', '[]', 'not JSON']:
            with patch("app.services.email_generator.call_llm", return_value=response):
                with self.assertRaises(LLMResponseError):
                    generate_email("Resume", "Job", "apply", "professional")
        with self.assertRaises(ValueError):
            generate_email(" ", "Job", "apply", "professional")


class EmailAndDraftAPITests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        self.engine_patch = patch.object(main, "engine", self.engine)
        self.engine_patch.start()
        self.key_patch = patch.object(settings, "LLM_API_KEY", "test-key")
        self.key_patch.start()
        self.gemini_patch = patch("app.services.llm_client.genai.Client")
        self.gemini = self.gemini_patch.start().return_value.__enter__.return_value
        self.email_response = json.dumps(EMAIL)
        self.fact_response = '{"warnings": []}'

        def provider_response(**kwargs):
            system = kwargs["config"].system_instruction
            text = self.fact_response if system.startswith("You review factual grounding") else self.email_response
            return SimpleNamespace(text=text)

        self.gemini.models.generate_content.side_effect = provider_response
        self.embedding_patch = patch("app.ml.scorer.get_embedding", return_value=[1, 0])
        self.encoder = self.embedding_patch.start()

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
            db.flush()
            profile = Profile(user_id=first.id, raw_resume_text="Python developer building APIs and SQL databases", parsed_data={"skills": ["Python", "SQL"]})
            job = Job(user_id=first.id, title="Engineer", company="Example", description="Python SQL")
            other_job = Job(user_id=second.id, title="Other", description="Other role")
            db.add_all([profile, job, other_job])
            db.commit()
            self.user_id, self.other_id, self.job_id, self.other_job_id = first.id, second.id, job.id, other_job.id
        self.headers = {"Authorization": f"Bearer {create_access_token({'sub': 'first@example.com'})}"}
        self.other_headers = {"Authorization": f"Bearer {create_access_token({'sub': 'second@example.com'})}"}

    def tearDown(self):
        self.context.__exit__(None, None, None)
        main.app.dependency_overrides.clear()
        main.app.dependency_overrides.update(self.overrides)
        self.embedding_patch.stop()
        self.gemini_patch.stop()
        self.key_patch.stop()
        self.engine_patch.stop()
        self.engine.dispose()

    def generate(self, headers=None, **updates):
        return self.client.post("/api/email/generate", headers=headers or self.headers,
                                json={"job_id": self.job_id, "situation": "apply", "tone": "professional", **updates})

    def test_generation_verification_scoring_and_persistence(self):
        response = self.generate(custom_notes="Keep it concise")
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertEqual(result["subject_line"], EMAIL["subject_line"])
        self.assertEqual(result["body"], EMAIL["body"])
        self.assertEqual(result["hallucination_warnings"], [])
        self.assertGreaterEqual(result["match_score"], 0)
        self.assertLessEqual(result["match_score"], 100)
        self.assertEqual(self.encoder.call_count, 3)
        self.assertEqual(self.gemini.models.generate_content.call_count, 2)
        fact_prompt = self.gemini.models.generate_content.call_args_list[1].kwargs["contents"]
        self.assertIn(EMAIL["subject_line"], fact_prompt)
        self.assertIn(EMAIL["body"], fact_prompt)
        with Session(self.engine) as db:
            draft = db.query(Draft).one()
            self.assertEqual(draft.id, result["draft_id"])
            self.assertEqual(draft.user_id, self.user_id)
            self.assertEqual(draft.job_id, self.job_id)
            self.assertEqual(draft.match_score, result["match_score"])

    def test_unverified_claims_are_returned_as_warnings(self):
        self.fact_response = '{"warnings": ["Unverified claim: managed a team of 20."]}'
        response = self.generate()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["hallucination_warnings"], ["Unverified claim: managed a team of 20."])
        with Session(self.engine) as db:
            self.assertEqual(db.query(Draft).count(), 1)

    def test_failed_generation_or_verification_saves_nothing(self):
        self.email_response = "not JSON"
        self.assertEqual(self.generate().status_code, 502)
        self.email_response = json.dumps(EMAIL)
        self.fact_response = '{}'
        self.assertEqual(self.generate().status_code, 502)
        self.encoder.assert_not_called()
        with Session(self.engine) as db:
            self.assertEqual(db.query(Draft).count(), 0)

    def test_missing_key_or_model_failure_saves_nothing(self):
        with patch.object(settings, "LLM_API_KEY", "dev_llm_key"):
            self.assertEqual(self.generate().status_code, 503)
        with patch("app.ml.scorer.get_embedding", side_effect=EmbeddingError("Model unavailable")):
            self.assertEqual(self.generate().status_code, 503)
        with Session(self.engine) as db:
            self.assertEqual(db.query(Draft).count(), 0)

    def test_generation_rejects_missing_or_foreign_job_and_missing_profile(self):
        self.assertEqual(self.generate(job_id=999999).status_code, 404)
        self.assertEqual(self.generate(job_id=self.other_job_id).status_code, 404)
        self.assertEqual(self.generate(headers=self.other_headers, job_id=self.other_job_id).status_code, 404)
        self.gemini.models.generate_content.assert_not_called()

    def test_draft_listing_and_retrieval(self):
        first, second = self.generate().json(), self.generate().json()
        listed = self.client.get("/api/drafts/", headers=self.headers)
        self.assertEqual(listed.status_code, 200)
        self.assertEqual([draft["id"] for draft in listed.json()], [second["draft_id"], first["draft_id"]])
        draft = self.client.get(f"/api/drafts/{first['draft_id']}", headers=self.headers)
        self.assertEqual(draft.status_code, 200)
        self.assertEqual(draft.json()["body"], EMAIL["body"])
        self.assertIsNotNone(draft.json()["created_at"])
        self.assertEqual(self.client.get("/api/drafts/", headers=self.other_headers).json(), [])

    def test_draft_edits_preserve_unset_fields_and_clear_stale_score(self):
        result = self.generate().json()
        url = f"/api/drafts/{result['draft_id']}"
        response = self.client.put(url, headers=self.headers, json={"subject_line": "New subject"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["body"], EMAIL["body"])
        self.assertEqual(response.json()["match_score"], result["match_score"])
        self.assertIsNotNone(response.json()["updated_at"])
        response = self.client.put(url, headers=self.headers, json={"body": "Revised email", "tone": "confident", "situation": "cold_email"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["body"], "Revised email")
        self.assertEqual(response.json()["tone"], "confident")
        self.assertIsNone(response.json()["match_score"])
        self.assertEqual(self.client.put(url, headers=self.headers, json={"subject_line": None}).status_code, 200)
        self.assertIsNone(self.client.get(url, headers=self.headers).json()["subject_line"])

    def test_other_users_cannot_read_edit_or_delete_drafts(self):
        result = self.generate().json()
        url = f"/api/drafts/{result['draft_id']}"
        self.assertEqual(self.client.get(url, headers=self.other_headers).status_code, 404)
        self.assertEqual(self.client.put(url, headers=self.other_headers, json={"body": "Intrusion"}).status_code, 404)
        self.assertEqual(self.client.delete(url, headers=self.other_headers).status_code, 404)
        self.assertEqual(self.client.get(url, headers=self.headers).status_code, 200)

    def test_delete_removes_owned_draft_only(self):
        result = self.generate().json()
        url = f"/api/drafts/{result['draft_id']}"
        response = self.client.delete(url, headers=self.headers)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.content, b"")
        self.assertEqual(self.client.get(url, headers=self.headers).status_code, 404)
        with Session(self.engine) as db:
            self.assertEqual(db.query(Draft).count(), 0)
            self.assertIsNotNone(db.get(Job, self.job_id))
            self.assertEqual(db.query(Profile).count(), 1)

    def test_invalid_payloads_cannot_modify_required_fields_or_ownership(self):
        result = self.generate().json()
        url = f"/api/drafts/{result['draft_id']}"
        for payload in [{"body": None}, {"body": " "}, {"tone": None}, {"situation": ""}, {"user_id": self.other_id}, {"job_id": self.other_job_id}, {"match_score": 100}]:
            self.assertEqual(self.client.put(url, headers=self.headers, json=payload).status_code, 422)
        self.assertEqual(self.generate(job_id=0).status_code, 422)
        self.assertEqual(self.generate(tone=" ").status_code, 422)
        self.assertEqual(self.generate(situation="").status_code, 422)

    def test_tracker_status_persists_and_rejects_invalid_updates(self):
        result = self.generate().json()
        url = f"/api/drafts/{result['draft_id']}"
        original = self.client.get(url, headers=self.headers).json()
        self.assertEqual(original["status"], "Draft")
        response = self.client.put(url, headers=self.headers, json={"status": "Interview"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "Interview")
        self.assertEqual(response.json()["body"], original["body"])
        self.assertEqual(response.json()["match_score"], original["match_score"])
        self.assertEqual(self.client.get(url, headers=self.headers).json()["status"], "Interview")
        with Session(self.engine) as db:
            self.assertEqual(db.get(Draft,result["draft_id"]).status, "Interview")
        for value in [None, "Unknown", ""]:
            self.assertEqual(self.client.put(url,headers=self.headers,json={"status":value}).status_code,422)

    def test_all_routes_require_authentication(self):
        self.assertEqual(self.client.post("/api/email/generate", json={"job_id": self.job_id, "situation": "apply", "tone": "professional"}).status_code, 401)
        self.assertEqual(self.client.get("/api/drafts/").status_code, 401)
        self.assertEqual(self.client.get("/api/drafts/1").status_code, 401)
        self.assertEqual(self.client.put("/api/drafts/1", json={"body": "Email"}).status_code, 401)
        self.assertEqual(self.client.delete("/api/drafts/1").status_code, 401)
        self.gemini.models.generate_content.assert_not_called()
