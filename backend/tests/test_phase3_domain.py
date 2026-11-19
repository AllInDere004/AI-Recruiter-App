import json
import socket
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from app.database import Base
import app.models.draft
import app.models.profile
from app.models.discovery import ExternalJobListing, Notification, SavedJob
from app.models.intelligence import ResumeVersion
from app.models.job import Job
from app.models.user import User
from app.providers.base import ProviderError
from app.providers.himalayas import HimalayasProvider
from app.providers.jooble import JoobleProvider
from app.services.application_service import create_application, update_application
from app.services.job_import import FetchedPage, ImportSecurityError, extract_job_text, fetch_public_page, validate_public_https_url
from app.services.recommendations import recommend
from app.services.reminders import create_reminder, process_due, update_reminder, utc_datetime


def public_answers(host, port, type=0):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))]


class ProviderAndImportTests(unittest.TestCase):
    def test_himalayas_normalizes_filters_sanitizes_and_deduplicates(self):
        future = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp())
        payload = {"totalCount": 2, "jobs": [
            {"guid": "himalayas-1", "title": "<b>Remote Python Engineer</b>",
             "companyName": "Example", "companySlug": "example", "employmentType": "Full Time",
             "minSalary": 100000, "maxSalary": 150000, "currency": "USD", "salaryPeriod": "annual",
             "seniority": ["Mid-level"], "locationRestrictions": [{"name": "India"}],
             "timezoneRestrictions": ["UTC+5:30"], "categories": ["Python", "APIs"],
             "parentCategories": ["Engineering"], "description": "<script>ignore</script><p>Build APIs</p>",
             "pubDate": 1794045600, "expiryDate": future,
             "applicationLink": "https://example.com/apply"},
            {"guid": "himalayas-1", "title": "Duplicate", "description": "Duplicate",
             "expiryDate": future, "applicationLink": "https://example.com/duplicate"},
        ]}
        requests = []
        provider = HimalayasProvider(api_key="synthetic", base_url="https://himalayas.app/jobs/api",
            requester=lambda params: (requests.append(params) or (200, json.dumps(payload).encode(), {})))
        result = provider.search(keywords="python", location="India", job_type="Full-time", sort="newest")
        self.assertEqual(len(result.jobs), 1)
        self.assertEqual(result.jobs[0].provider, "himalayas")
        self.assertEqual(result.jobs[0].title, "Remote Python Engineer")
        self.assertEqual(result.jobs[0].application_url, "https://example.com/apply")
        self.assertEqual(result.jobs[0].provider_url, "https://himalayas.app")
        self.assertNotIn("<", result.jobs[0].description)
        self.assertEqual(requests[0]["country"], "India")
        self.assertEqual(requests[0]["employment_type"], "Full Time")
        self.assertEqual(requests[0]["sort"], "recent")

    def test_himalayas_errors_are_safe_and_rate_limit_is_preserved(self):
        provider = HimalayasProvider(api_key="private-key", base_url="https://himalayas.app/jobs/api",
            requester=lambda params: (401, b"private provider body", {}))
        with self.assertRaises(ProviderError) as caught:
            provider.search(keywords="python", location="India")
        self.assertNotIn("private-key", str(caught.exception))
        self.assertNotIn("provider body", str(caught.exception))
        limited = HimalayasProvider(api_key="private-key", base_url="https://himalayas.app/jobs/api",
            requester=lambda params: (429, b"private provider body", {"Retry-After": "17"}))
        with self.assertRaises(ProviderError) as caught:
            limited.search(keywords="python", location="India")
        self.assertEqual(caught.exception.status_code, 429)
        self.assertEqual(caught.exception.retry_after, 17)

    def test_jooble_normalizes_sanitizes_and_deduplicates(self):
        payload = {"totalCount": 2, "jobs": [
            {"id": 7, "title": "<b>Python Developer</b>", "company": "Example",
             "location": "Bengaluru", "snippet": "<script>ignore</script><p>Build APIs</p>",
             "salary": "INR 10-15L", "type": "Full-time", "link": "https://in.jooble.org/jdp/7",
             "updated": "2026-11-07T10:00:00Z", "source": "Jooble"},
            {"id": 7, "title": "Duplicate", "link": "https://in.jooble.org/jdp/7"},
        ]}
        provider = JoobleProvider(api_key="secret", base_url="https://in.jooble.org/api",
                                  requester=lambda request: (200, json.dumps(payload).encode()))
        result = provider.search(keywords="python", location="India")
        self.assertEqual(len(result.jobs), 1)
        self.assertEqual(result.jobs[0].title, "Python Developer")
        self.assertNotIn("<", result.jobs[0].description)
        self.assertIn("Build APIs", result.jobs[0].description)

    def test_provider_errors_never_include_key_or_payload(self):
        provider = JoobleProvider(api_key="private-key", base_url="https://in.jooble.org/api",
                                  requester=lambda request: (403, b"private provider body"))
        with self.assertRaises(ProviderError) as caught:
            provider.search(keywords="python", location="India")
        self.assertNotIn("private-key", str(caught.exception))
        self.assertNotIn("provider body", str(caught.exception))

    def test_ssrf_rejects_private_loopback_linklocal_and_credentials(self):
        for address in ["127.0.0.1", "10.0.0.4", "169.254.169.254", "::1", "fe80::1"]:
            resolver = lambda host, port, type=0, address=address: [(socket.AF_INET6 if ":" in address else socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, port))]
            with self.assertRaises(ImportSecurityError):
                validate_public_https_url("https://example.com/job", resolver=resolver)
        with self.assertRaises(ImportSecurityError):
            validate_public_https_url("https://user:pass@example.com/job", resolver=public_answers)
        with self.assertRaises(ImportSecurityError):
            validate_public_https_url("https://example.com:8443/job", resolver=public_answers)

    def test_redirect_destination_is_revalidated(self):
        calls = []
        def fetch(url, limit):
            calls.append(url)
            if len(calls) == 1:
                return FetchedPage(url, "text/html", b"", 302, "https://internal.example/job")
            return FetchedPage(url, "text/html", b"ok content for a public job page", 200)
        def validate(url):
            if "internal" in url:
                raise ImportSecurityError("private")
            return url, "example.com", ["93.184.216.34"]
        with patch("app.services.job_import.validate_public_https_url", side_effect=validate):
            with self.assertRaises(ImportSecurityError):
                fetch_public_page("https://example.com/job", fetch_once=fetch)

    def test_structured_jobposting_is_preferred_and_html_removed(self):
        body = b'''<html><script type="application/ld+json">{"@type":"JobPosting","title":"Engineer","description":"<p>Build safe APIs</p>","hiringOrganization":{"name":"Example"},"jobLocation":{"address":{"addressLocality":"Pune","addressCountry":"IN"}},"url":"https://example.com/apply"}</script><p>Navigation</p></html>'''
        result = extract_job_text(FetchedPage("https://example.com/job", "text/html", body, 200))
        self.assertTrue(result["structured"])
        self.assertEqual(result["title"], "Engineer")
        self.assertEqual(result["text"], "Build safe APIs")


class ApplicationReminderRecommendationTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        event.listen(self.engine, "connect", lambda dbapi, _: dbapi.execute("PRAGMA foreign_keys=ON"))
        Base.metadata.create_all(self.engine)
        with Session(self.engine) as db:
            user = User(email="phase3@example.com", hashed_password="unused")
            db.add(user); db.flush(); self.user_id = user.id
            resume = ResumeVersion(user_id=user.id, revision=1, fingerprint="r" * 64,
                data_json={"skills": ["Python"], "experience": [], "education": []},
                source_text="Skills: Python", source_metadata_json={}, approved=True)
            listing = ExternalJobListing(provider="jooble", provider_job_id="1", title="Python Engineer",
                company="Example", location="Remote India", job_type="Full-time", skills_json=["Python", "Docker"],
                description="Python required. Docker preferred.", provider_url="https://example.com/job",
                application_url="https://example.com/apply", content_fingerprint="f" * 64,
                fetched_at=datetime.now(timezone.utc), is_active=True, normalized_json={})
            db.add_all([resume, listing]); db.flush(); self.listing_id = listing.id
            job = Job(user_id=user.id, title=listing.title, company=listing.company,
                      description=listing.description, extracted_skills={"required_skills": ["Python"], "preferred_skills": ["Docker"]})
            db.add(job); db.flush()
            saved = SavedJob(user_id=user.id, listing_id=listing.id, job_id=job.id, tags_json=[])
            db.add(saved); db.commit(); self.saved_id = saved.id

    def tearDown(self):
        self.engine.dispose()

    def test_transition_requires_submission_confirmation_and_stale_version_fails(self):
        with Session(self.engine) as db:
            app = create_application(db, self.user_id, self.saved_id); db.commit(); app_id = app.id
            payload = SimpleNamespace(expected_version=1, model_dump=lambda exclude_unset: {"expected_version": 1, "status": "Applied", "confirm_submission": False})
            with self.assertRaises(HTTPException):
                update_application(db, self.user_id, app_id, payload)
            db.rollback()
            confirmed = SimpleNamespace(expected_version=1, model_dump=lambda exclude_unset: {"expected_version": 1, "status": "Applied", "confirm_submission": True})
            updated = update_application(db, self.user_id, app_id, confirmed); db.commit()
            self.assertEqual(updated.status, "Applied")
            self.assertIsNotNone(updated.submitted_at)
            with self.assertRaises(HTTPException):
                update_application(db, self.user_id, app_id, confirmed)

    def test_reminder_timezone_and_delivery_are_idempotent(self):
        with self.assertRaises(HTTPException):
            utc_datetime(datetime(2026, 11, 7, 10, 0), "Asia/Calcutta")
        converted = utc_datetime(datetime.fromisoformat("2026-11-07T10:00:00+05:30"), "Asia/Calcutta")
        self.assertEqual(converted.hour, 4)
        with Session(self.engine) as db:
            app = create_application(db, self.user_id, self.saved_id); db.flush()
            payload = SimpleNamespace(application_id=app.id, kind="follow_up", title="Follow up", note=None,
                due_at=datetime.now(timezone.utc) - timedelta(minutes=1), timezone="Asia/Calcutta")
            create_reminder(db, self.user_id, payload); db.commit()
            self.assertEqual(process_due(db, user_id=self.user_id), 1); db.commit()
            self.assertEqual(process_due(db, user_id=self.user_id), 0); db.commit()
            self.assertEqual(db.query(Notification).count(), 1)

    def test_recommendations_use_real_active_listing_and_explain_gaps(self):
        with Session(self.engine) as db:
            results = recommend(db, self.user_id)
            self.assertEqual(results[0]["listing_id"], self.listing_id)
            self.assertIn("compatibility_score", results[0])
            self.assertIn("hiring success", results[0]["disclaimer"])
            self.assertIn("Docker", results[0]["missing_required"])
