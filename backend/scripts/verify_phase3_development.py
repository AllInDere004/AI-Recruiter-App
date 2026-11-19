"""Apply and test Phase 2 + Phase 3 migrations only on the authorized dev branch.

Every credential-bearing CLI response is captured in memory. No connection string,
password, token, private row, or provider key is printed or written to the report.
Synthetic data is rolled back.
"""
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from uuid import uuid4

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import resolve_neon_host
from app.models.user import User
from app.models.profile import Profile
from app.models.job import Job
from app.models.draft import Draft
from app.models.intelligence import CareerReport, GenerationVersion, ResumeVersion
from app.models.discovery import (
    Application, ApplicationEvent, ExternalJobListing, JobPreference, Notification,
    RecommendationCache, Reminder, SavedJob,
)


PROJECT = "divine-dust-28314320"
BRANCH_NAME = "phase3-smart-job-discovery-20261107"
BRANCH_ID = "br-flat-fog-azl6aupx"
ORIGINAL = {"users", "profiles", "jobs", "drafts", "recruiter_users", "recruiter_profiles",
            "recruiter_jobs", "recruiter_drafts", "recruiter_sessions", "recruiter_migrations"}
PHASE2 = {"resume_versions", "career_reports", "generation_versions"}
MODELS = (ResumeVersion, CareerReport, GenerationVersion, ExternalJobListing, SavedJob,
          JobPreference, Application, ApplicationEvent, Reminder, Notification, RecommendationCache)
NEW = {model.__tablename__ for model in MODELS}
REPORT = {"checked_at_utc": datetime.now(timezone.utc).isoformat(), "branch": BRANCH_NAME,
          "branch_id": BRANCH_ID, "schema_only": True, "production_schema_modified": False,
          "production_backup_taken": False,
          "production_activation": "Requires verified backup/restore and explicit migration approval."}
STAGE = "initialization"


def cli(*args):
    executable = shutil.which("neon.cmd") or shutil.which("neon")
    if not executable:
        raise RuntimeError("CLI unavailable")
    result = subprocess.run([executable, *args, "--project-id", PROJECT, "--output", "json"],
                            cwd=ROOT, capture_output=True, text=True, timeout=90)
    if result.returncode:
        raise RuntimeError("CLI metadata request failed")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return result.stdout.strip()


def endpoint(value):
    return (value or "").replace("-pooler.", ".")


def original_metadata(connection):
    inspector = inspect(connection)
    return {name: {"columns": [(c["name"], str(c["type"]), c["nullable"], c["default"])
                               for c in inspector.get_columns(name)],
                   "foreign_keys": inspector.get_foreign_keys(name),
                   "indexes": inspector.get_indexes(name),
                   "unique": inspector.get_unique_constraints(name),
                   "checks": inspector.get_check_constraints(name)} for name in sorted(ORIGINAL)}


def counts(connection):
    return {name: connection.execute(text('SELECT count(*) FROM public."' + name + '"')).scalar_one()
            for name in sorted(ORIGINAL | NEW)}


def assert_model_metadata(connection):
    inspector = inspect(connection)
    for model in MODELS:
        table = model.__table__
        actual = {column["name"]: column for column in inspector.get_columns(table.name)}
        assert set(actual) == set(table.columns.keys())
        for column in table.columns:
            assert actual[column.name]["nullable"] == column.nullable
        unique = {tuple(item["column_names"]) for item in inspector.get_unique_constraints(table.name)}
        for constraint in table.constraints:
            if constraint.__class__.__name__ == "UniqueConstraint":
                assert tuple(constraint.columns.keys()) in unique
        checks = {item["name"] for item in inspector.get_check_constraints(table.name)}
        expected_checks = {item.name for item in table.constraints if item.__class__.__name__ == "CheckConstraint"}
        assert expected_checks <= checks
        foreign = {(tuple(item["constrained_columns"]), item["referred_table"], tuple(item["referred_columns"]))
                   for item in inspector.get_foreign_keys(table.name)}
        for constraint in table.foreign_key_constraints:
            expected = (tuple(element.parent.name for element in constraint.elements),
                        constraint.elements[0].column.table.name,
                        tuple(element.column.name for element in constraint.elements))
            assert expected in foreign
        indexes = {tuple(item["column_names"]) for item in inspector.get_indexes(table.name)}
        assert all(tuple(index.columns.keys()) in indexes for index in table.indexes)


def rejected(db, model):
    failed = False
    try:
        with db.begin_nested():
            db.add(model); db.flush()
    except IntegrityError:
        failed = True
    assert failed


def synthetic_checks(connection):
    transaction = connection.begin()
    db = Session(bind=connection)
    checks = []
    try:
        suffix = uuid4().hex
        first = User(email=f"phase3-{suffix}@example.invalid", hashed_password="not-a-login")
        second = User(email=f"phase3-other-{suffix}@example.invalid", hashed_password="not-a-login")
        db.add_all([first, second]); db.flush()
        profile = Profile(user_id=first.id, full_name="Synthetic", raw_resume_text="Skills: Python", parsed_data={"skills": ["Python"]})
        job = Job(user_id=first.id, title="Synthetic Engineer", description="Python and SQL", extracted_skills={"required_skills": ["Python"]})
        db.add_all([profile, job]); db.flush()
        resume = ResumeVersion(user_id=first.id, profile_id=profile.id, revision=1, fingerprint="a" * 64,
            data_json={"skills": ["Python"]}, source_text="Skills: Python", source_metadata_json={}, approved=True)
        db.add(resume); db.flush()
        email = GenerationVersion(user_id=first.id, resume_version_id=resume.id, job_id=job.id,
            lineage_id=str(uuid4()), revision=1, kind="email", content_json={"body": "Synthetic"},
            warnings_json=[], approved=True, model="synthetic")
        cover = GenerationVersion(user_id=first.id, resume_version_id=resume.id, job_id=job.id,
            lineage_id=str(uuid4()), revision=1, kind="cover_letter", content_json={"body": "Synthetic"},
            warnings_json=[], approved=True, model="synthetic")
        report = CareerReport(user_id=first.id, resume_version_id=resume.id, job_id=job.id, kind="match",
            algorithm_version="synthetic", profile_version="a" * 64, job_version="b" * 64,
            input_hash="c" * 64, result_json={"overall_score": 80})
        db.add_all([email, cover, report]); db.flush()
        listing = ExternalJobListing(provider="synthetic", provider_job_id=suffix, title="Synthetic Engineer",
            company="Example", location="Remote India", skills_json=["Python"], description="Python and SQL",
            provider_url="https://example.invalid/job", application_url="https://example.invalid/apply",
            content_fingerprint="d" * 64, is_active=True, normalized_json={})
        db.add(listing); db.flush()
        saved = SavedJob(user_id=first.id, listing_id=listing.id, job_id=job.id, tags_json=["synthetic"])
        preference = JobPreference(user_id=first.id, roles_json=["Engineer"], locations_json=["India"],
                                   job_types_json=[], experience_levels_json=[])
        db.add_all([saved, preference]); db.flush()
        application = Application(user_id=first.id, saved_job_id=saved.id, job_id=job.id, status="Applied",
            submitted_at=datetime.now(timezone.utc), application_date=datetime.now(timezone.utc),
            resume_version_id=resume.id, email_version_id=email.id, cover_letter_version_id=cover.id)
        db.add(application); db.flush()
        activity = ApplicationEvent(user_id=first.id, application_id=application.id,
                                    event_type="status_changed", from_status="Preparing", to_status="Applied", context_json={})
        reminder = Reminder(user_id=first.id, application_id=application.id, kind="follow_up", title="Follow up",
            due_at=datetime.now(timezone.utc), timezone="Asia/Calcutta", delivery_key=f"reminder:{suffix}")
        db.add_all([activity, reminder]); db.flush()
        notification = Notification(user_id=first.id, reminder_id=reminder.id, title="Follow up",
            message="Synthetic", delivery_key=f"notification:{suffix}")
        cache = RecommendationCache(user_id=first.id, listing_id=listing.id, resume_version_id=resume.id,
            algorithm_version="synthetic", input_hash="e" * 64, result_json={"ranking_score": 80},
            listing_fetched_at=listing.fetched_at, expires_at=datetime.now(timezone.utc) + timedelta(hours=1))
        db.add_all([notification, cache]); db.flush()
        checks.extend(["listing and saved-job persistence", "approved document ownership links",
                       "application event history", "reminder and notification persistence",
                       "recommendation cache persistence"])
        rejected(db, SavedJob(user_id=first.id, listing_id=listing.id, tags_json=[]))
        rejected(db, Application(user_id=second.id, saved_job_id=saved.id, status="Saved"))
        rejected(db, Application(user_id=first.id, saved_job_id=saved.id + 999999, status="Invalid"))
        rejected(db, Notification(user_id=first.id, reminder_id=reminder.id, title="Duplicate",
                                  message="Synthetic", delivery_key=notification.delivery_key))
        checks.extend(["duplicate saved job rejected", "cross-user application link rejected",
                       "invalid application rejected", "duplicate notification delivery rejected"])
        return checks
    finally:
        db.close()
        if transaction.is_active:
            transaction.rollback()


def apply_sql(engine, filename):
    sql = (BACKEND / "migrations" / filename).read_text()
    assert not re.search(r"\b(?:DROP\s+TABLE|TRUNCATE|DELETE\s+FROM|ALTER\s+TABLE)\b", sql, re.I)
    raw = engine.raw_connection()
    try:
        raw.autocommit = True
        with raw.cursor() as cursor:
            cursor.execute(sql)
    finally:
        raw.close()


def run():
    global STAGE
    STAGE = "branch identity verification"
    branch = cli("branches", "get", BRANCH_ID)
    assert isinstance(branch, dict) and branch["id"] == BRANCH_ID and branch["name"] == BRANCH_NAME
    assert branch.get("project_id") == PROJECT and not branch.get("default") and not branch.get("primary")
    assert branch.get("init_source") == "parent-schema"
    dev_computes = cli("postgres", "computes", "list", "--branch", BRANCH_ID)
    prod_computes = cli("postgres", "computes", "list", "--branch", "production")
    production_hosts = {endpoint(item.get("host")) for item in prod_computes}
    production_hosts.add(endpoint(make_url(settings.DATABASE_URL).host))
    expected_hosts = {endpoint(item.get("host")) for item in dev_computes}
    assert expected_hosts and not (expected_hosts & production_hosts)
    connection = cli("connection-string", BRANCH_ID, "--database-name", "neondb", "--ssl", "require")
    if isinstance(connection, dict):
        connection = connection.get("connection_string") or connection.get("connection_uri") or connection.get("uri")
    assert isinstance(connection, str)
    url = make_url(connection)
    assert endpoint(url.host) in expected_hosts and endpoint(url.host) not in production_hosts
    assert url.database == "neondb" and "-pooler." not in url.host
    assert url.query.get("sslmode") in {"require", "verify-ca", "verify-full"}
    REPORT.update({"branch_verified": True, "production_endpoint_excluded": True})
    engine = create_engine(url.set(drivername="postgresql+psycopg2"), connect_args={"connect_timeout": 20})
    event.listen(engine, "do_connect", resolve_neon_host)
    try:
        STAGE = "development schema inventory"
        with engine.connect() as connection_obj:
            assert connection_obj.execute(text("SELECT 1")).scalar_one() == 1
            assert connection_obj.execute(text("SELECT current_database()") ).scalar_one() == "neondb"
            assert connection_obj.connection.driver_connection.info.ssl_in_use
            before = original_metadata(connection_obj)
            present = set(inspect(connection_obj).get_table_names())
            assert ORIGINAL <= present
        STAGE = "phase 2 dependency migration"
        if not PHASE2 <= present:
            assert not (present & PHASE2)
            apply_sql(engine, "002_career_intelligence.sql")
            REPORT["phase2_migration_applied_this_run"] = True
        else:
            REPORT["phase2_migration_applied_this_run"] = False
        REPORT["phase2_schema_present"] = True
        STAGE = "phase 3 development-only migration"
        with engine.connect() as connection_obj:
            present = set(inspect(connection_obj).get_table_names())
        phase3 = NEW - PHASE2
        if not phase3 <= present:
            assert not (present & phase3)
            apply_sql(engine, "003_smart_job_discovery.sql")
            REPORT["phase3_migration_applied_this_run"] = True
        else:
            REPORT["phase3_migration_applied_this_run"] = False
        REPORT["phase3_schema_present"] = True
        STAGE = "schema constraints and original preservation"
        with engine.connect() as connection_obj:
            assert original_metadata(connection_obj) == before
            assert_model_metadata(connection_obj)
            connection_obj.rollback()
            baseline = counts(connection_obj); connection_obj.rollback()
            STAGE = "synthetic rollback tests"
            REPORT["synthetic_checks"] = synthetic_checks(connection_obj)
            assert counts(connection_obj) == baseline
            connection_obj.rollback()
        REPORT.update({"status": "passed", "select_1": True, "tls_enabled": True,
            "original_tables_preserved": sorted(ORIGINAL), "new_tables_verified": sorted(NEW),
            "synthetic_rows_rolled_back": True, "new_metadata_matches_models": True})
    finally:
        engine.dispose()


def write_report():
    path = ROOT / "PHASE3_MIGRATION_TEST.md"
    path.write_text("# Phase 3 development migration verification\n\n"
        "Metadata only. Credential-bearing CLI responses were captured in memory and never written here.\n\n"
        "```json\n" + json.dumps(REPORT, indent=2) + "\n```\n\n"
        "Production remains unchanged. Production activation still requires a verified backup/restore checkpoint and explicit migration approval.\n",
        encoding="utf-8")


if __name__ == "__main__":
    try:
        run()
    except Exception as error:
        REPORT.update({"status": "failed", "stage": STAGE, "error_type": type(error).__name__,
                       "sqlstate": getattr(getattr(error, "orig", error), "pgcode", None)})
        write_report()
        print("Development migration verification failed; raw diagnostics withheld.")
        sys.exit(1)
    write_report()
    print("Development migration verification passed; production excluded; synthetic rows rolled back.")
