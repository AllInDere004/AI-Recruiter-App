"""Authenticated local-development smoke test against the configured backend.

This intentionally creates synthetic records in the selected development database.
It never prints credentials, tokens, resume content, or provider responses.
"""
from __future__ import annotations

from io import BytesIO
import os
import sys

import pymupdf as fitz
import requests


BASE = os.environ.get("LOCAL_API_BASE", "http://127.0.0.1:8002")
EMAIL = os.environ.get("LOCAL_E2E_EMAIL", "")
PASSWORD = os.environ.get("LOCAL_E2E_PASSWORD", "")
SECOND_EMAIL = os.environ.get("LOCAL_E2E_SECOND_EMAIL", "")


class Client(requests.Session):
    def request(self, method, url, **kwargs):
        kwargs.setdefault("timeout", 120)
        target = f"{BASE}{url}" if url.startswith("/") else url
        return super().request(method, target, **kwargs)


def require(response: requests.Response, expected: int | tuple[int, ...], label: str):
    allowed = (expected,) if isinstance(expected, int) else expected
    if response.status_code not in allowed:
        detail = ""
        try:
            value = response.json()
            detail = str(value.get("detail", "")) if isinstance(value, dict) else ""
        except Exception:
            pass
        raise RuntimeError(f"{label} returned HTTP {response.status_code}: {detail[:160]}")
    return response.json() if response.content else None


def pdf_bytes() -> bytes:
    with fitz.open() as document:
        page = document.new_page()
        page.insert_text(
            (72, 72),
            "Local Activation Candidate\n"
            "Software engineer with Python, FastAPI, PostgreSQL, React, TypeScript, SQL, and API design.\n"
            "Built secure web applications, analytics dashboards, and automated testing workflows.\n"
            "Experience: Software Engineer, Example Labs, 2022-2026.\n"
            "Education: Bachelor of Computer Science.",
        )
        return document.tobytes()


def auth_headers(client: httpx.Client, email: str):
    require(client.post("/api/auth/register", json={"email": email, "password": PASSWORD}), 201, "register")
    token = require(client.post("/api/auth/login", json={"email": email, "password": PASSWORD}), 200, "login")["access_token"]
    return {"Authorization": f"Bearer {token}"}


def main() -> int:
    if not EMAIL or not PASSWORD or not SECOND_EMAIL:
        raise RuntimeError("Synthetic test identities were not supplied")
    with Client() as client:
        require(client.get("/ready"), 200, "readiness")
        require(client.get("/api/discovery/status"), 401, "unauthenticated discovery")
        require(client.get("/api/interviews/status"), 401, "unauthenticated interviews")
        headers = auth_headers(client, EMAIL)

        discovery = require(client.get("/api/discovery/status", headers=headers), 200, "discovery status")
        interviews = require(client.get("/api/interviews/status", headers=headers), 200, "interview status")
        intelligence = require(client.get("/api/intelligence/status", headers=headers), 200, "career status")
        assert discovery["enabled"] and discovery["ready"] and discovery["provider"] == "himalayas"
        assert discovery["provider_configured"]
        assert interviews["enabled"] and interviews["ready"] and not interviews["gmail_enabled"]
        assert intelligence["enabled"] and intelligence["ready"]
        print("PASS authenticated feature status and disabled Gmail")

        profile = require(client.post(
            "/api/resume/upload", headers=headers,
            files={"file": ("local-activation-resume.pdf", BytesIO(pdf_bytes()), "application/pdf")},
        ), 200, "live Gemini resume parsing")
        assert profile["parsed_data"] and profile["parsed_data"].get("skills")
        resume = require(client.post("/api/intelligence/resumes", headers=headers, json={"approved": True}), 200, "approve resume")
        assert resume["approved"]
        print("PASS live Gemini resume parsing and approved resume selection")

        search = None
        for keywords in ("software engineer", "python"):
            candidate = require(client.get("/api/discovery/search", headers=headers, params={
                "keywords": keywords, "location": "India", "page": 1, "page_size": 10,
                "sort": "newest",
            }), 200, "Himalayas search")
            if candidate["jobs"]:
                search = candidate
                break
        if not search:
            raise RuntimeError("Himalayas returned no jobs for bounded smoke-test queries")
        assert search["provider"] == "himalayas" and search["page"] == 1
        page_two = require(client.get("/api/discovery/search", headers=headers, params={
            "keywords": "software engineer", "location": "India", "page": 2,
            "page_size": 5, "sort": "title",
        }), 200, "Himalayas pagination")
        assert page_two["provider"] == "himalayas" and page_two["page"] == 2
        listing = search["jobs"][0]
        saved = require(client.post("/api/discovery/saved-jobs", headers=headers, json={
            "listing_id": listing["id"], "notes": "Local activation verification", "tags": ["local-test"]
        }), 201, "save job")
        preferences = require(client.put("/api/discovery/preferences", headers=headers, json={
            "roles": ["Software Engineer"], "locations": ["Remote"], "remote_policy": "remote",
            "experience_levels": [], "job_types": [listing.get("job_type") or "Full Time"],
            "timezone": "Asia/Calcutta",
        }), 200, "job preferences")
        assert preferences["roles"]
        recommendations = require(client.get("/api/discovery/recommendations", headers=headers), 200, "resume-job recommendations")
        assert "recommendations" in recommendations
        print("PASS real Himalayas search, filters, pagination, bookmark, and resume-job recommendations")

        report = require(client.post("/api/intelligence/analyze", headers=headers, json={
            "job_id": saved["job_id"], "resume_version_id": resume["id"], "include_explanation": False,
        }), 200, "career match")
        assert report["result"]["overall_score"] is not None
        application = require(client.post("/api/applications/", headers=headers, json={
            "saved_job_id": saved["id"], "notes": "Local activation application"
        }), 201, "create application")
        application = require(client.put(f"/api/applications/{application['id']}", headers=headers, json={
            "expected_version": application["version"], "status": "Applied", "confirm_submission": True,
            "resume_version_id": resume["id"],
        }), 200, "mark application applied")
        application = require(client.put(f"/api/applications/{application['id']}", headers=headers, json={
            "expected_version": application["version"], "status": "Interview",
        }), 200, "advance application")
        assert application["status"] == "Interview"
        print("PASS career matching and application tracking")

        session = require(client.post("/api/interviews/sessions", headers=headers, json={
            "resume_version_id": resume["id"], "job_id": saved["job_id"],
            "interview_type": "technical", "difficulty": "beginner", "question_count": 1,
        }), 201, "Gemini interview question")
        assert len(session["questions"]) == 1
        question = session["questions"][0]
        session = require(client.put(
            f"/api/interviews/sessions/{session['id']}/questions/{question['id']}/answer",
            headers=headers, json={"answer": "I would clarify requirements, design a small FastAPI service, use PostgreSQL transactions, add tests, and measure reliability."},
        ), 200, "submit interview answer")
        session = require(client.post(f"/api/interviews/sessions/{session['id']}/evaluate", headers=headers), 200, "Gemini interview feedback")
        evaluation = session["questions"][0]["evaluation"]
        assert session["status"] == "evaluated" and 0 <= evaluation["practice_score"] <= 100
        history = require(client.get("/api/interviews/sessions", headers=headers), 200, "interview history")
        assert history["total"] >= 1
        print("PASS Gemini questions, answer submission, feedback, score, and history")

        analytics = require(client.get("/api/analytics/career", headers=headers), 200, "career analytics")
        filtered = require(client.get("/api/analytics/career", headers=headers, params={"stage": "Interview"}), 200, "filtered analytics")
        summary = require(client.get("/api/applications/analytics/summary", headers=headers), 200, "application analytics")
        assert analytics["funnel"]["saved"] >= 1 and analytics["funnel"]["interviews"] >= 1
        assert analytics["interview_practice"]["sessions"] >= 1
        assert filtered["filters"]["stage"] == "Interview" and summary["total_applications"] >= 1
        print("PASS real Neon career funnel, filters, application statistics, and interview metrics")

        second_headers = auth_headers(client, SECOND_EMAIL)
        require(client.get(f"/api/applications/{application['id']}", headers=second_headers), 404, "application ownership")
        require(client.get(f"/api/interviews/sessions/{session['id']}", headers=second_headers), 404, "interview ownership")
        require(client.get(f"/api/intelligence/reports/{report['id']}", headers=second_headers), 404, "report ownership")
        assert require(client.get("/api/applications/", headers=second_headers), 200, "second user applications") == []
        assert require(client.get("/api/interviews/sessions", headers=second_headers), 200, "second user interviews")["total"] == 0
        print("PASS authentication and cross-user data isolation")

        jobs = require(client.get("/api/jobs/", headers=headers), 200, "existing jobs route")
        profile_check = require(client.get("/api/profile/me", headers=headers), 200, "existing profile route")
        assert jobs and profile_check["id"] == profile["id"]
        print("PASS existing profile and jobs regression paths")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"FAIL local activation: {type(error).__name__}: {str(error)[:300]}", file=sys.stderr)
        raise SystemExit(1)
