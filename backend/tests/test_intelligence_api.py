"""Phase 2 ownership/versioning checks: isolated SQLite and mocked AI only."""
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import main
from app.config import settings
from app.database import get_db
from app.models.draft import Draft
from app.models.intelligence import CareerReport, GenerationVersion, ResumeVersion
from app.models.job import Job
from app.models.profile import Profile
from app.models.user import User
from app.services.auth_service import create_access_token
from app.services.career_repository import resume_source
from app.api.intelligence import _requests
from test_resume_parser import make_pdf


SOURCE = "Jane Doe\nPython developer\nSkills: Python, SQL\nEducation: Computer Science"
PROFILE = {"full_name": "Jane Doe", "skills": ["Python", "SQL"], "education": [], "experience": []}


class CareerAPITests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        event.listen(self.engine, "connect", lambda dbapi, _: dbapi.execute("PRAGMA foreign_keys=ON"))
        self.engine_patch = patch.object(main, "engine", self.engine)
        self.flag = patch.object(settings, "ENABLE_CAREER_INTELLIGENCE", True)
        self.engine_patch.start()
        self.flag.start()
        self.original = main.app.dependency_overrides.copy()
        def test_db():
            # Match the application's SessionLocal configuration.
            with Session(self.engine, autoflush=False) as db:
                yield db
        main.app.dependency_overrides[get_db] = test_db
        self.context = TestClient(main.app)
        self.client = self.context.__enter__()
        with Session(self.engine) as db:
            a = User(email="career@example.com", hashed_password="unused")
            b = User(email="other-career@example.com", hashed_password="unused")
            db.add_all([a,b]); db.flush()
            self.a, self.b = a.id, b.id
            db.add_all([Profile(user_id=a.id, full_name="Jane Doe", raw_resume_text=SOURCE, parsed_data=PROFILE),
                        Profile(user_id=b.id, full_name="Jane Doe", raw_resume_text=SOURCE, parsed_data=PROFILE)])
            ja = Job(user_id=a.id, title="Developer", description="Required skills: Python, SQL. Preferred: Docker.", extracted_skills={"required_skills":["Python","SQL"],"preferred_skills":["Docker"]})
            jb = Job(user_id=b.id, title="Private job", description="Python", extracted_skills={"required_skills":["Python"]})
            db.add_all([ja,jb]); db.commit()
            self.job, self.other_job = ja.id,jb.id
        self.headers = {"Authorization":f"Bearer {create_access_token({'sub':'career@example.com'})}"}
        self.other = {"Authorization":f"Bearer {create_access_token({'sub':'other-career@example.com'})}"}
        _requests.clear()

    def tearDown(self):
        self.context.__exit__(None,None,None)
        main.app.dependency_overrides.clear()
        main.app.dependency_overrides.update(self.original)
        self.flag.stop(); self.engine_patch.stop(); self.engine.dispose()
        _requests.clear()

    def approve_resume(self, headers=None):
        response = self.client.post("/api/intelligence/resumes",json={"approved":True},headers=headers or self.headers)
        self.assertEqual(response.status_code,200,response.text)
        return response.json()

    def generated(self, **overrides):
        payload = {"job_id":self.job,"kind":"email",**overrides}
        with patch("app.services.document_generation.generate_document",return_value={"content":{"subject_line":"Application","body":"Python developer","evidence_ids":[]},"warnings":[],"policy_version":"test"}):
            return self.client.post("/api/intelligence/documents/generate",json=payload,headers=self.headers)

    def test_disabled_and_missing_schema_do_not_break_phase1(self):
        with patch.object(settings,"ENABLE_CAREER_INTELLIGENCE",False):
            self.assertEqual(self.client.get("/api/intelligence/status",headers=self.headers).json(),{"enabled":False,"ready":False})
            self.assertEqual(self.client.post("/api/intelligence/resumes",json={},headers=self.headers).status_code,503)
        with patch("app.services.career_repository.schema_ready",return_value=False):
            self.assertEqual(self.client.get("/api/intelligence/reports",headers=self.headers).status_code,503)
        self.assertEqual(self.client.get("/api/jobs/",headers=self.headers).status_code,200)

    def test_all_phase2_routes_require_authentication(self):
        for path in ["status","resumes","resumes/1/source","reports","reports/1","documents","documents/1/export"]:
            self.assertEqual(self.client.get("/api/intelligence/"+path).status_code,401)
        for path,body in [("resumes",{}),("analyze",{}),("documents/generate",{"job_id":self.job,"kind":"email"})]:
            self.assertEqual(self.client.post("/api/intelligence/"+path,json=body).status_code,401)

    def test_snapshot_is_immutable_deduplicated_and_owner_scoped(self):
        first = self.approve_resume()
        self.assertNotIn("source_text",first)
        self.assertEqual(self.approve_resume()["id"],first["id"])
        saved = self.client.put("/api/profile/me",headers=self.headers,json={"full_name":"Reviewed Name"})
        self.assertEqual(saved.status_code,200,saved.text)
        history = self.client.get("/api/intelligence/resumes",headers=self.headers).json()
        self.assertEqual(len(history),2)
        self.assertEqual(history[0]["parent_id"],first["id"])
        self.assertEqual(history[1]["data"]["full_name"],"Jane Doe")
        self.assertEqual(self.client.get("/api/intelligence/resumes",headers=self.other).json(),[])
        with Session(self.engine) as db:
            newest = db.get(ResumeVersion,history[0]["id"])
            self.assertEqual(newest.source_text,"")
            self.assertEqual(resume_source(db,newest),SOURCE)

    def test_report_persistence_dedup_ats_and_cross_user_isolation(self):
        resume = self.approve_resume()
        response = self.client.post("/api/intelligence/analyze",headers=self.headers,json={"job_id":self.job})
        self.assertEqual(response.status_code,200,response.text)
        report = response.json()
        self.assertEqual(report["resume_version_id"],resume["id"])
        self.assertIn("ats",report["result"])
        repeated = self.client.post("/api/intelligence/analyze",headers=self.headers,json={"job_id":self.job})
        self.assertEqual(repeated.json()["id"],report["id"])
        self.assertEqual(self.client.get(f"/api/intelligence/reports/{report['id']}",headers=self.other).status_code,404)
        self.assertEqual(self.client.get(f"/api/intelligence/reports?job_id={self.job}",headers=self.other).status_code,404)
        self.assertEqual(self.client.post("/api/intelligence/analyze",headers=self.headers,json={"job_id":self.other_job}).status_code,404)
        self.assertEqual(self.client.post("/api/intelligence/analyze",headers=self.other,json={"resume_version_id":resume["id"]}).status_code,404)
        ats = self.client.post("/api/intelligence/analyze",headers=self.headers,json={})
        self.assertEqual(ats.status_code,200,ats.text)
        self.assertEqual(ats.json()["kind"],"ats")
        self.assertIsNone(ats.json()["job_id"])

    def test_unreviewed_resume_cannot_generate_or_analyze(self):
        response = self.client.post("/api/intelligence/resumes",headers=self.headers,json={"approved":False})
        self.assertEqual(response.status_code,200)
        self.assertEqual(self.client.post("/api/intelligence/analyze",headers=self.headers,json={"job_id":self.job}).status_code,409)
        self.assertEqual(self.generated().status_code,409)

    def test_document_history_conflict_approval_export_and_existing_draft_sync(self):
        self.approve_resume()
        response = self.generated()
        self.assertEqual(response.status_code,200,response.text)
        first = response.json()
        self.assertEqual(self.client.get(f"/api/intelligence/documents/{first['id']}/export",headers=self.headers).status_code,409)
        edit = self.client.put(f"/api/intelligence/documents/{first['id']}",headers=self.headers,json={"body":"Python and SQL developer"})
        self.assertEqual(edit.status_code,200,edit.text)
        second = edit.json()
        self.assertNotEqual(first["id"],second["id"])
        self.assertEqual(second["parent_id"],first["id"])
        self.assertEqual(second["revision"],2)
        self.assertEqual(self.client.put(f"/api/intelligence/documents/{first['id']}",headers=self.headers,json={"body":"stale"}).status_code,409)
        approved = self.client.put(f"/api/intelligence/documents/{second['id']}",headers=self.headers,json={"approved":True})
        self.assertEqual(approved.status_code,200,approved.text)
        self.assertTrue(approved.json()["approved"])
        self.assertIsNotNone(approved.json()["draft_id"])
        drafts = self.client.get("/api/drafts/",headers=self.headers).json()
        self.assertEqual(len(drafts),1)
        self.assertEqual(drafts[0]["body"],"Python and SQL developer")
        for fmt in ["pdf","docx"]:
            downloaded = self.client.get(f"/api/intelligence/documents/{second['id']}/export?format={fmt}",headers=self.headers)
            self.assertEqual(downloaded.status_code,200,downloaded.text if downloaded.status_code!=200 else "")
            self.assertGreater(len(downloaded.content),100)
            self.assertEqual(downloaded.headers["cache-control"],"private, no-store")
        with Session(self.engine) as db:
            self.assertEqual(db.get(GenerationVersion,first["id"]).content_json["body"],"Python developer")

    def test_cross_user_documents_and_parent_references_are_hidden(self):
        self.approve_resume()
        doc = self.generated().json()
        self.assertEqual(self.client.get("/api/intelligence/documents",headers=self.other).json(),[])
        self.assertEqual(self.client.put(f"/api/intelligence/documents/{doc['id']}",headers=self.other,json={"approved":True}).status_code,404)
        self.assertEqual(self.client.get(f"/api/intelligence/documents/{doc['id']}/export",headers=self.other).status_code,404)
        self.assertEqual(self.generated(job_id=self.other_job).status_code,404)
        self.approve_resume(self.other)
        response = self.client.post("/api/intelligence/documents/generate",headers=self.other,json={"job_id":self.other_job,"kind":"email","parent_id":doc["id"]})
        self.assertEqual(response.status_code,404)

    def test_bad_weights_and_client_owner_fields_are_rejected(self):
        self.approve_resume()
        for weights in [{"unknown":1},{"required_skills":-1}]:
            response = self.client.post("/api/intelligence/analyze",headers=self.headers,json={"job_id":self.job,"weights":weights})
            self.assertEqual(response.status_code,422,response.text)
        self.assertEqual(self.client.post("/api/intelligence/resumes",headers=self.headers,json={"approved":True,"user_id":self.b}).status_code,422)

    def test_ai_rate_limit_is_bounded_per_user(self):
        self.approve_resume()
        with patch.object(settings,"CAREER_AI_REQUESTS_PER_MINUTE",1):
            self.assertEqual(self.generated().status_code,200)
            response = self.generated()
            self.assertEqual(response.status_code,429)
            self.assertEqual(response.headers["retry-after"],"60")

    def test_optional_profile_snapshot_preserves_original_before_first_edit(self):
        response = self.client.put("/api/profile/me",headers=self.headers,json={"full_name":"Reviewed Name"})
        self.assertEqual(response.status_code,200,response.text)
        versions = self.client.get("/api/intelligence/resumes",headers=self.headers).json()
        self.assertEqual(len(versions),2)
        self.assertEqual(versions[1]["data"]["full_name"],"Jane Doe")
        self.assertFalse(versions[1]["approved"])
        self.assertTrue(versions[0]["approved"])

    def test_validation_errors_never_reflect_password_or_document_input(self):
        password = "SYNTHETIC_PRIVATE_PASSWORD_" * 8
        response = self.client.post("/api/auth/register",json={"email":"invalid-email", "password":password})
        self.assertEqual(response.status_code,422)
        self.assertNotIn(password,response.text)
        marker = "SYNTHETIC_PRIVATE_DOCUMENT_BODY"
        response = self.client.put("/api/intelligence/documents/1",headers=self.headers,json={"body":[marker]})
        self.assertEqual(response.status_code,422)
        self.assertNotIn(marker,response.text)
        for detail in response.json()["detail"]:
            self.assertEqual(set(detail),{"loc","msg","type"})

    def test_historical_source_is_private_owner_scoped_and_resolves_deduplicated_text(self):
        original = self.approve_resume()
        self.client.put("/api/profile/me",headers=self.headers,json={"full_name":"Reviewed Name"})
        latest = self.client.get("/api/intelligence/resumes",headers=self.headers).json()[0]
        path=f"/api/intelligence/resumes/{latest['id']}/source"
        response=self.client.get(path,headers=self.headers)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json(),{"resume_version_id":latest["id"],"source_text":SOURCE})
        self.assertEqual(response.headers["cache-control"],"private, no-store")
        self.assertEqual(self.client.get(path,headers=self.other).status_code,404)
        self.assertEqual(self.client.get(path).status_code,401)
        with patch.object(settings,"ENABLE_CAREER_INTELLIGENCE",False):
            self.assertEqual(self.client.get(path,headers=self.headers).status_code,503)

    def test_upload_preserves_private_metadata_and_original_resume(self):
        content=make_pdf("Synthetic Python developer")
        with patch("app.api.resume.extract_profile_from_text",return_value=PROFILE):
            uploaded=self.client.post("/api/resume/upload",headers=self.headers,
                files={"file":("C:\\private\\resume.pdf",content,"application/pdf")})
        self.assertEqual(uploaded.status_code,200,uploaded.text)
        history=self.client.get("/api/intelligence/resumes",headers=self.headers).json()
        self.assertEqual(len(history),2)
        self.assertEqual(history[0]["metadata"]["filename"],"resume.pdf")
        self.assertEqual(history[0]["metadata"]["size_bytes"],len(content))
        self.assertEqual(len(history[0]["metadata"]["sha256"]),64)
        old=self.client.get(f"/api/intelligence/resumes/{history[1]['id']}/source",headers=self.headers)
        self.assertEqual(old.json()["source_text"],SOURCE)
