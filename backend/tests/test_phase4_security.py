import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from cryptography.fernet import Fernet
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import main
from app.config import settings
from app.database import get_db
from app.models.advanced import GmailConnection, UserRole
from app.models.intelligence import GenerationVersion, ResumeVersion
from app.models.job import Job
from app.models.user import User
from app.services.auth_service import create_access_token
from app.services.gmail_service import finish_oauth, start_oauth


class Phase4SecurityTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        event.listen(self.engine, "connect", lambda dbapi, _: dbapi.execute("PRAGMA foreign_keys=ON"))
        self.engine_patch = patch.object(main, "engine", self.engine); self.engine_patch.start()
        self.flags = [patch.object(settings, "ENABLE_ADVANCED_FEATURES", True),
                      patch.object(settings, "ENABLE_JOB_DISCOVERY", True)]
        for value in self.flags: value.start()
        self.original = main.app.dependency_overrides.copy()
        def test_db():
            with Session(self.engine) as db: yield db
        main.app.dependency_overrides[get_db] = test_db
        self.context = TestClient(main.app); self.client = self.context.__enter__()
        with Session(self.engine) as db:
            user = User(email="security@example.com", hashed_password="unused")
            other = User(email="security-other@example.com", hashed_password="unused")
            db.add_all([user, other]); db.commit(); self.user_id, self.other_id = user.id, other.id
        self.headers = {"Authorization": f"Bearer {create_access_token({'sub': 'security@example.com'})}"}
        self.other = {"Authorization": f"Bearer {create_access_token({'sub': 'security-other@example.com'})}"}

    def tearDown(self):
        self.context.__exit__(None, None, None)
        main.app.dependency_overrides.clear(); main.app.dependency_overrides.update(self.original)
        for value in reversed(self.flags): value.stop()
        self.engine_patch.stop(); self.engine.dispose()

    def test_notification_preferences_are_private_and_versioned(self):
        initial = self.client.get("/api/notifications/preferences", headers=self.headers)
        self.assertEqual(initial.status_code, 200)
        payload = {"categories": {"interview": False}, "email_enabled": False,
                   "timezone": "Asia/Calcutta", "quiet_hours": {}}
        saved = self.client.put("/api/notifications/preferences", headers=self.headers, json=payload)
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertFalse(saved.json()["categories"]["interview"])
        self.assertTrue(self.client.get("/api/notifications/preferences", headers=self.other).json()["categories"]["interview"])
        stale = self.client.put("/api/notifications/preferences", headers=self.headers,
            json={**payload, "expected_version": 99})
        self.assertEqual(stale.status_code, 409)

    def test_admin_is_denied_by_default_and_audited_when_granted(self):
        self.assertEqual(self.client.get("/api/admin/overview", headers=self.headers).status_code, 403)
        self.assertEqual(self.client.get("/api/admin/overview").status_code, 401)
        with Session(self.engine) as db:
            db.add(UserRole(user_id=self.user_id, role="admin")); db.commit()
        result = self.client.get("/api/admin/overview", headers=self.headers)
        self.assertEqual(result.status_code, 200, result.text)
        self.assertNotIn("resume_text", result.text.casefold())
        self.assertNotIn("answer_text", result.text.casefold())
        self.assertNotIn("email_body", result.text.casefold())
        events = self.client.get("/api/admin/audit-events", headers=self.headers)
        self.assertEqual(events.status_code, 200)
        self.assertEqual(events.json()[0]["action"], "admin.overview.viewed")
        self.assertEqual(self.client.get("/api/admin/overview", headers=self.other).status_code, 403)

    def test_gmail_is_disabled_without_server_configuration(self):
        status = self.client.get("/api/integrations/gmail/status", headers=self.headers)
        self.assertEqual(status.status_code, 200)
        self.assertFalse(status.json()["enabled"])
        self.assertEqual(self.client.post("/api/integrations/gmail/authorize", headers=self.headers).status_code, 503)
        self.assertEqual(self.client.post("/api/integrations/gmail/send", headers=self.headers, json={
            "generation_version_id": 1, "recipient": "person@example.com", "subject": "Review",
            "body": "Reviewed body", "confirm_review": True, "idempotency_key": "1234567890123456"}).status_code, 503)

    def test_oauth_state_is_one_time_and_refresh_token_is_encrypted(self):
        key = Fernet.generate_key().decode()
        patches = [patch.object(settings, "ENABLE_GMAIL", True), patch.object(settings, "GOOGLE_CLIENT_ID", "client"),
            patch.object(settings, "GOOGLE_CLIENT_SECRET", "secret"),
            patch.object(settings, "GOOGLE_OAUTH_REDIRECT_URI", "https://app.example.com/settings/gmail/callback"),
            patch.object(settings, "GMAIL_TOKEN_ENCRYPTION_KEY", key)]
        with patches[0], patches[1], patches[2], patches[3], patches[4], Session(self.engine) as db:
            url = start_oauth(db, self.user_id)
            state = url.split("state=")[1].split("&")[0]
            from urllib.parse import unquote
            state = unquote(state)
            connection = finish_oauth(db, state, "code",
                exchanger=lambda code, verifier: {"access_token": "access", "refresh_token": "refresh-private", "expires_in": 3600, "scope": "openid email https://www.googleapis.com/auth/gmail.send"},
                identity_fetcher=lambda token: {"sub": "google-subject", "email": "candidate@example.com"})
            self.assertNotIn("refresh-private", connection.encrypted_refresh_token)
            with self.assertRaises(HTTPException):
                finish_oauth(db, state, "code", exchanger=lambda *_: {}, identity_fetcher=lambda *_: {})

    def test_gmail_send_requires_exact_approved_document_and_is_idempotent(self):
        key = Fernet.generate_key().decode()
        with Session(self.engine) as db:
            resume = ResumeVersion(user_id=self.user_id, revision=1, fingerprint="z"*64, data_json={},
                source_text="resume", source_metadata_json={}, approved=True)
            job = Job(user_id=self.user_id, title="Engineer", company="Example", description="Role", extracted_skills={})
            db.add_all([resume, job]); db.flush()
            document = GenerationVersion(user_id=self.user_id, resume_version_id=resume.id, job_id=job.id,
                lineage_id="line", revision=1, kind="email", content_json={"subject_line":"Hello","body":"Reviewed body"},
                warnings_json=[], approved=True, model="test")
            db.add(document); db.flush()
            encrypted = Fernet(key.encode()).encrypt(b"refresh").decode()
            db.add(GmailConnection(user_id=self.user_id, google_subject="sub", email_hint="me@example.com",
                encrypted_refresh_token=encrypted, scopes_json=["https://www.googleapis.com/auth/gmail.send"]))
            db.commit(); document_id = document.id
        configured = [patch.object(settings, "ENABLE_GMAIL", True), patch.object(settings, "GOOGLE_CLIENT_ID", "client"),
            patch.object(settings, "GOOGLE_CLIENT_SECRET", "secret"), patch.object(settings, "GOOGLE_OAUTH_REDIRECT_URI", "https://app.example.com/callback"),
            patch.object(settings, "GMAIL_TOKEN_ENCRYPTION_KEY", key)]
        payload = {"generation_version_id": document_id, "recipient": "person@example.com", "subject": "Hello",
                   "body": "Reviewed body", "confirm_review": True, "idempotency_key": "send-approval-123456"}
        with configured[0], configured[1], configured[2], configured[3], configured[4], patch("app.api.integrations.send_message", return_value={"id":"provider-id"}):
            sent = self.client.post("/api/integrations/gmail/send", headers=self.headers, json=payload)
            self.assertEqual(sent.status_code, 200, sent.text)
            duplicate = self.client.post("/api/integrations/gmail/send", headers=self.headers, json=payload)
            self.assertTrue(duplicate.json()["duplicate"])
            changed = self.client.post("/api/integrations/gmail/send", headers=self.headers,
                json={**payload, "body": "Changed", "idempotency_key": "send-approval-654321"})
            self.assertEqual(changed.status_code, 409)
