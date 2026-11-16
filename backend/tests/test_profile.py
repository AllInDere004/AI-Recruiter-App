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
from app.models.profile import Profile
from app.models.user import User
from app.schemas.profile import ParsedData
from app.services.auth_service import create_access_token
from app.services.llm_client import LLMConfigurationError, LLMError, LLMResponseError, call_llm, extract_json
from app.services.profile_extractor import extract_profile_from_text
from test_resume_parser import make_pdf


PROFILE_DATA = {
    "full_name": "Jane Doe", "email": "jane@example.com", "phone": None,
    "summary": "Python developer", "skills": ["Python", "SQL"],
    "experience": [{"company": "Example", "role": "Developer"}],
    "education": [{"degree": "Computer Science"}],
}


class LLMProfileExtractionTests(unittest.TestCase):
    def test_json_extraction_handles_fences_prose_and_braces(self):
        value = {"summary": 'Built {tools} with "JSON"', "skills": ["Python"]}
        encoded = json.dumps(value)
        for text in [encoded, f"```json\n{encoded}\n```", f"Here is the profile: {encoded} End."]:
            self.assertEqual(extract_json(text), value)
        for text in ["not JSON", "[]", "null", "{invalid}"]:
            with self.assertRaises(LLMResponseError):
                extract_json(text)

    def test_gemini_receives_key_model_system_instruction_and_json_mode(self):
        with patch.object(settings, "LLM_API_KEY", "test-key"), patch("app.services.llm_client.genai.Client") as factory:
            client = factory.return_value.__enter__.return_value
            client.models.generate_content.return_value = SimpleNamespace(text=' {"skills": []} ')
            self.assertEqual(call_llm("prompt", "system", json_mode=True), '{"skills": []}')
            self.assertEqual(factory.call_args.kwargs["api_key"], "test-key")
            self.assertEqual(factory.call_args.kwargs["http_options"].api_version, "v1beta")
            request = client.models.generate_content.call_args.kwargs
            self.assertEqual(request["model"], settings.LLM_MODEL)
            self.assertEqual(request["contents"], "prompt")
            self.assertEqual(request["config"].system_instruction, "system")
            self.assertEqual(request["config"].response_mime_type, "application/json")

    def test_missing_key_never_calls_provider(self):
        with patch.object(settings, "LLM_API_KEY", "dev_llm_key"), patch("app.services.llm_client.genai.Client") as factory:
            with self.assertRaises(LLMConfigurationError):
                call_llm("prompt")
            factory.assert_not_called()

    def test_provider_errors_do_not_expose_credentials_or_resume(self):
        with patch.object(settings, "LLM_API_KEY", "test-key"), patch("app.services.llm_client.genai.Client") as factory:
            client = factory.return_value.__enter__.return_value
            client.models.generate_content.side_effect = TimeoutError("secret resume and credentials")
            with self.assertRaises(LLMError) as caught:
                call_llm("prompt")
            self.assertNotIn("secret", str(caught.exception))

    def test_empty_provider_response_is_rejected(self):
        with patch.object(settings, "LLM_API_KEY", "test-key"), patch("app.services.llm_client.genai.Client") as factory:
            factory.return_value.__enter__.return_value.models.generate_content.return_value = SimpleNamespace(text=None)
            with self.assertRaises(LLMResponseError):
                call_llm("prompt")

    def test_template_and_schema_validation(self):
        with patch("app.services.profile_extractor.call_llm", return_value=json.dumps(PROFILE_DATA)) as call:
            result = extract_profile_from_text("Jane Doe\nPython developer")
            self.assertEqual(result, PROFILE_DATA)
            self.assertIn("Jane Doe\nPython developer", call.call_args.args[0])
            self.assertTrue(call.call_args.kwargs["json_mode"])
        with patch("app.services.profile_extractor.call_llm", return_value='{"skills": "not-an-array"}'):
            with self.assertRaises(LLMResponseError):
                extract_profile_from_text("Resume")
        with self.assertRaises(ValueError):
            extract_profile_from_text(" ")

    def test_list_defaults_are_not_shared(self):
        first, second = ParsedData(), ParsedData()
        first.skills.append("Python")
        self.assertEqual(second.skills, [])


class ResumeAndProfileAPITests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        self.engine_patch = patch.object(main, "engine", self.engine)
        self.engine_patch.start()
        # Phase 1 profile behavior must not depend on feature flags from a
        # developer's effective local environment.
        self.feature_patches = [
            patch.object(settings, "ENABLE_CAREER_INTELLIGENCE", False),
            patch.object(settings, "ENABLE_JOB_DISCOVERY", False),
            patch.object(settings, "ENABLE_ADVANCED_FEATURES", False),
        ]
        for feature_patch in self.feature_patches:
            feature_patch.start()
        self.key_patch = patch.object(settings, "LLM_API_KEY", "test-key")
        self.key_patch.start()
        self.gemini_patch = patch("app.services.llm_client.genai.Client")
        self.factory = self.gemini_patch.start()
        self.gemini = self.factory.return_value.__enter__.return_value
        self.gemini.models.generate_content.return_value = SimpleNamespace(text=json.dumps(PROFILE_DATA))

        def test_db():
            with Session(self.engine) as db:
                yield db

        self.overrides = main.app.dependency_overrides.copy()
        main.app.dependency_overrides[get_db] = test_db
        self.context = TestClient(main.app)
        self.client = self.context.__enter__()
        with Session(self.engine) as db:
            first = User(email="jane@example.com", hashed_password="test-hash")
            second = User(email="other@example.com", hashed_password="test-hash")
            db.add_all([first, second])
            db.commit()
            self.user_id, self.other_id = first.id, second.id
        self.headers = {"Authorization": f"Bearer {create_access_token({'sub': 'jane@example.com'})}"}
        self.other_headers = {"Authorization": f"Bearer {create_access_token({'sub': 'other@example.com'})}"}

    def tearDown(self):
        self.context.__exit__(None, None, None)
        main.app.dependency_overrides.clear()
        main.app.dependency_overrides.update(self.overrides)
        self.gemini_patch.stop()
        self.key_patch.stop()
        for feature_patch in reversed(self.feature_patches):
            feature_patch.stop()
        self.engine_patch.stop()
        self.engine.dispose()

    def upload(self, text="Jane Doe\nPython developer", headers=None):
        return self.client.post("/api/resume/upload", headers=headers or self.headers,
                                files={"file": ("resume.pdf", make_pdf(text), "application/pdf")})

    def test_upload_extracts_pdf_calls_gemini_and_persists_profile(self):
        response = self.upload()
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["user_id"], self.user_id)
        self.assertEqual(data["full_name"], "Jane Doe")
        self.assertEqual(data["parsed_data"], PROFILE_DATA)
        self.assertIn("Python developer", data["raw_resume_text"])
        self.assertIsNotNone(data["updated_at"])
        request = self.gemini.models.generate_content.call_args.kwargs
        self.assertIn("Jane Doe", request["contents"])
        reread = self.client.get("/api/profile/me", headers=self.headers)
        self.assertEqual(reread.json(), data)
        with Session(self.engine) as db:
            self.assertEqual(db.query(Profile).count(), 1)
            self.assertEqual(db.query(Profile).one().parsed_data, PROFILE_DATA)

    def test_reupload_updates_existing_record(self):
        original = self.upload().json()
        updated_data = {**PROFILE_DATA, "full_name": "Updated Name", "skills": ["Rust"]}
        self.gemini.models.generate_content.return_value = SimpleNamespace(text=json.dumps(updated_data))
        updated = self.upload("Updated Name\nRust developer")
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["id"], original["id"])
        self.assertEqual(updated.json()["parsed_data"]["skills"], ["Rust"])
        with Session(self.engine) as db:
            self.assertEqual(db.query(Profile).count(), 1)

    def test_manual_edit_preserves_unset_fields_and_raw_text(self):
        original = self.upload().json()
        response = self.client.put("/api/profile/me", headers=self.headers, json={"full_name": "Edited Name"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["full_name"], "Edited Name")
        self.assertEqual(response.json()["raw_resume_text"], original["raw_resume_text"])
        self.assertEqual(response.json()["parsed_data"], original["parsed_data"])
        response = self.client.put("/api/profile/me", headers=self.headers, json={"parsed_data": {"skills": ["Go"]}})
        self.assertEqual(response.json()["parsed_data"], {"skills": ["Go"]})
        self.assertEqual(response.json()["full_name"], "Edited Name")
        response = self.client.put("/api/profile/me", headers=self.headers, json={"full_name": None, "parsed_data": None})
        self.assertIsNone(response.json()["full_name"])
        self.assertIsNone(response.json()["parsed_data"])

    def test_profiles_are_isolated_between_accounts(self):
        own = self.upload().json()
        self.assertEqual(self.client.get("/api/profile/me", headers=self.other_headers).status_code, 404)
        self.assertEqual(self.client.put("/api/profile/me", headers=self.other_headers, json={"full_name": "Intruder"}).status_code, 404)
        other = self.upload(headers=self.other_headers).json()
        self.assertEqual(other["user_id"], self.other_id)
        self.assertNotEqual(other["id"], own["id"])
        self.assertEqual(self.client.put("/api/profile/me", headers=self.headers, json={"user_id": self.other_id}).status_code, 422)
        self.assertEqual(self.client.get("/api/profile/me", headers=self.headers).json()["id"], own["id"])

    def test_all_routes_require_authentication(self):
        self.assertEqual(self.client.get("/api/profile/me").status_code, 401)
        self.assertEqual(self.client.put("/api/profile/me", json={"full_name": "Name"}).status_code, 401)
        response = self.client.post("/api/resume/upload", files={"file": ("resume.pdf", make_pdf("Resume"), "application/pdf")})
        self.assertEqual(response.status_code, 401)
        self.gemini.models.generate_content.assert_not_called()

    def test_missing_profile_returns_404(self):
        self.assertEqual(self.client.get("/api/profile/me", headers=self.headers).status_code, 404)
        self.assertEqual(self.client.put("/api/profile/me", headers=self.headers, json={"parsed_data": {}}).status_code, 404)

    def test_invalid_uploads_never_call_gemini(self):
        for content, content_type, expected in [(b"text", "text/plain", 415), (b"corrupt", "application/pdf", 422), (b"", "application/pdf", 422), (make_pdf(""), "application/pdf", 422), (make_pdf("Secret", encrypted=True), "application/pdf", 422)]:
            with self.subTest(content_type=content_type, size=len(content)):
                response = self.client.post("/api/resume/upload", headers=self.headers, files={"file": ("resume.pdf", content, content_type)})
                self.assertEqual(response.status_code, expected, response.text)
        with patch("app.services.resume_parser.MAX_PDF_BYTES", 16):
            self.assertEqual(self.upload().status_code, 413)
        self.gemini.models.generate_content.assert_not_called()

    def test_provider_failure_does_not_overwrite_saved_profile(self):
        original = self.upload().json()
        for text in ["not JSON", '{"skills": "invalid"}', None]:
            self.gemini.models.generate_content.return_value = SimpleNamespace(text=text)
            self.assertEqual(self.upload("New resume").status_code, 502)
            self.assertEqual(self.client.get("/api/profile/me", headers=self.headers).json(), original)

    def test_missing_api_key_returns_503_without_creating_profile(self):
        with patch.object(settings, "LLM_API_KEY", "dev_llm_key"):
            response = self.upload()
        self.assertEqual(response.status_code, 503)
        self.factory.assert_not_called()
        with Session(self.engine) as db:
            self.assertEqual(db.query(Profile).count(), 0)
