"""Phase 3 authenticated API, ownership, persistence, and analytics checks."""
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import main
from app.config import settings
from app.database import get_db
from app.models.discovery import ExternalJobListing
from app.models.profile import Profile
from app.models.user import User
from app.providers.base import NormalizedJob, SearchPage
from app.services.auth_service import create_access_token


class FakeProvider:
    name = "himalayas"
    configured = True

    def search(self, **kwargs):
        item = NormalizedJob(provider="himalayas", provider_job_id="api-1", title="Python Engineer",
            company="Example", location="Bengaluru", job_type="Full-time", salary_text=None,
            experience_text=None, skills=["Python"], description="Build Python APIs.",
            published_at=datetime.now(timezone.utc), provider_url="https://example.com/job",
            application_url="https://example.com/apply", normalized={"source": "Himalayas"})
        return SearchPage([item], 1, kwargs.get("page", 1), kwargs.get("page_size", 20), "himalayas")


class Phase3APITests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        event.listen(self.engine, "connect", lambda dbapi, _: dbapi.execute("PRAGMA foreign_keys=ON"))
        self.engine_patch = patch.object(main, "engine", self.engine)
        self.flags = [patch.object(settings, "ENABLE_JOB_DISCOVERY", True),
                      patch.object(settings, "ENABLE_CAREER_INTELLIGENCE", True)]
        self.engine_patch.start()
        for flag in self.flags: flag.start()
        self.original = main.app.dependency_overrides.copy()
        def test_db():
            with Session(self.engine) as db:
                yield db
        main.app.dependency_overrides[get_db] = test_db
        self.context = TestClient(main.app)
        self.client = self.context.__enter__()
        with Session(self.engine) as db:
            a = User(email="phase3-api@example.com", hashed_password="unused")
            b = User(email="phase3-other@example.com", hashed_password="unused")
            db.add_all([a, b]); db.flush()
            db.add_all([Profile(user_id=a.id, full_name="Candidate", raw_resume_text="Skills: Python",
                                parsed_data={"full_name": "Candidate", "skills": ["Python"], "experience": [], "education": []}),
                        Profile(user_id=b.id, full_name="Other", raw_resume_text="Skills: Java",
                                parsed_data={"full_name": "Other", "skills": ["Java"], "experience": [], "education": []})])
            db.commit()
        self.headers = {"Authorization": f"Bearer {create_access_token({'sub': 'phase3-api@example.com'})}"}
        self.other = {"Authorization": f"Bearer {create_access_token({'sub': 'phase3-other@example.com'})}"}

    def tearDown(self):
        self.context.__exit__(None, None, None)
        main.app.dependency_overrides.clear(); main.app.dependency_overrides.update(self.original)
        for flag in reversed(self.flags): flag.stop()
        self.engine_patch.stop(); self.engine.dispose()

    def search_and_save(self):
        with patch("app.api.discovery._provider", return_value=FakeProvider()):
            response = self.client.get("/api/discovery/search?keywords=python&location=India", headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        listing = response.json()["jobs"][0]
        saved = self.client.post("/api/discovery/saved-jobs", headers=self.headers,
                                 json={"listing_id": listing["id"], "tags": ["priority"], "notes": "Review"})
        self.assertEqual(saved.status_code, 201, saved.text)
        return listing, saved.json()

    def test_status_and_private_routes_require_authentication(self):
        self.assertEqual(self.client.get("/api/discovery/status").status_code, 401)
        for path in ["/api/discovery/saved-jobs", "/api/discovery/preferences",
                     "/api/discovery/recommendations", "/api/applications/",
                     "/api/applications/reminders/list", "/api/applications/notifications/list",
                     "/api/applications/activity/list", "/api/applications/analytics/summary"]:
            self.assertEqual(self.client.get(path).status_code, 401, path)
        status = self.client.get("/api/discovery/status", headers=self.headers)
        self.assertEqual(status.status_code, 200)
        self.assertTrue(status.json()["ready"])

    def test_search_save_dedup_archive_and_cross_user_isolation(self):
        listing, saved = self.search_and_save()
        duplicate = self.client.post("/api/discovery/saved-jobs", headers=self.headers,
                                     json={"listing_id": listing["id"]})
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(self.client.get("/api/discovery/saved-jobs", headers=self.other).json(), [])
        self.assertEqual(self.client.put(f"/api/discovery/saved-jobs/{saved['id']}", headers=self.other,
                                         json={"archived": True}).status_code, 404)
        archived = self.client.put(f"/api/discovery/saved-jobs/{saved['id']}", headers=self.headers,
                                   json={"archived": True, "tags": ["later"]})
        self.assertIsNotNone(archived.json()["archived_at"])
        self.assertEqual(self.client.get("/api/discovery/saved-jobs", headers=self.headers).json(), [])
        self.assertEqual(len(self.client.get("/api/discovery/saved-jobs?archived=true", headers=self.headers).json()), 1)

    def test_application_confirmation_history_concurrency_and_analytics(self):
        _, saved = self.search_and_save()
        created = self.client.post("/api/applications/", headers=self.headers,
                                   json={"saved_job_id": saved["id"]})
        self.assertEqual(created.status_code, 201, created.text)
        app = created.json()
        denied = self.client.put(f"/api/applications/{app['id']}", headers=self.headers,
            json={"expected_version": app["version"], "status": "Applied", "confirm_submission": False})
        self.assertEqual(denied.status_code, 409)
        applied = self.client.put(f"/api/applications/{app['id']}", headers=self.headers,
            json={"expected_version": app["version"], "status": "Applied", "confirm_submission": True})
        self.assertEqual(applied.status_code, 200, applied.text)
        self.assertIsNotNone(applied.json()["submitted_at"])
        stale = self.client.put(f"/api/applications/{app['id']}", headers=self.headers,
            json={"expected_version": app["version"], "notes": "stale"})
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(self.client.get(f"/api/applications/{app['id']}", headers=self.other).status_code, 404)
        activity = self.client.get("/api/applications/activity/list", headers=self.headers).json()
        self.assertEqual([row["event_type"] for row in activity["events"]][:2], ["status_changed", "application_created"])
        analytics = self.client.get("/api/applications/analytics/summary", headers=self.headers).json()
        self.assertEqual(analytics["total_applications"], 1)
        self.assertEqual(analytics["submitted_applications"], 1)
        self.assertEqual(analytics["response_rate"], 0.0)

    def test_reminder_delivery_notification_and_owner_boundaries(self):
        _, saved = self.search_and_save()
        app = self.client.post("/api/applications/", headers=self.headers,
                               json={"saved_job_id": saved["id"]}).json()
        due = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        reminder = self.client.post("/api/applications/reminders", headers=self.headers, json={
            "application_id": app["id"], "kind": "follow_up", "title": "Follow up",
            "due_at": due, "timezone": "Asia/Calcutta"})
        self.assertEqual(reminder.status_code, 201, reminder.text)
        self.assertEqual(self.client.post("/api/applications/reminders/process-mine", headers=self.headers).json()["delivered"], 1)
        self.assertEqual(self.client.post("/api/applications/reminders/process-mine", headers=self.headers).json()["delivered"], 0)
        notes = self.client.get("/api/applications/notifications/list", headers=self.headers).json()
        self.assertEqual(len(notes), 1)
        self.assertEqual(self.client.get("/api/applications/notifications/list", headers=self.other).json(), [])
        self.assertEqual(self.client.put(f"/api/applications/reminders/{reminder.json()['id']}", headers=self.other,
            json={"expected_version": reminder.json()["version"], "action": "complete"}).status_code, 404)
        self.assertEqual(self.client.post("/api/applications/internal/process-reminders").status_code, 401)

    def test_manual_import_requires_review_and_safe_application_url(self):
        analysis = {"title": "Backend Engineer", "company": "Example", "location": "Pune",
                    "employment_type": "Full-time", "required_skills": ["Python"],
                    "preferred_skills": [], "experience_requirements": []}
        with patch("app.api.discovery.analyze_job_description", return_value=analysis):
            preview = self.client.post("/api/discovery/import/preview", headers=self.headers,
                json={"manual_text": "Backend Engineer at Example. Python required for building APIs."})
        self.assertEqual(preview.status_code, 200, preview.text)
        reviewed = preview.json()
        payload = {"preview_token": reviewed["preview_token"], "title": reviewed["title"],
            "company": reviewed["company"], "location": reviewed["location"], "job_type": reviewed["job_type"],
            "skills": reviewed["skills"], "description": reviewed["description"],
            "application_url": "https://example.com/apply", "tags": ["imported"]}
        with patch("app.api.discovery.validate_public_https_url", return_value=("https://example.com/apply", "example.com", ["93.184.216.34"])):
            saved = self.client.post("/api/discovery/import/save", headers=self.headers, json=payload)
        self.assertEqual(saved.status_code, 201, saved.text)
        self.assertEqual(saved.json()["listing"]["provider"], "url_import")

    def test_preferences_persist_and_are_owner_specific(self):
        payload = {"roles": ["Backend Engineer"], "locations": ["Pune"], "remote_policy": "hybrid",
                   "experience_levels": ["mid"], "job_types": ["Full-time"], "timezone": "Asia/Calcutta"}
        saved = self.client.put("/api/discovery/preferences", headers=self.headers, json=payload)
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertEqual(saved.json()["version"], 1)
        self.assertEqual(self.client.get("/api/discovery/preferences", headers=self.headers).json()["roles"], ["Backend Engineer"])
        self.assertEqual(self.client.get("/api/discovery/preferences", headers=self.other).json()["roles"], [])
