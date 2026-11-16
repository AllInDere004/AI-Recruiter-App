"""Credential-safe Phase 4 migration verification on the allowlisted schema-only branch."""
import json
import os
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
import app.models.draft
import app.models.discovery
from app.models.intelligence import CareerReport, GenerationVersion, ResumeVersion
from app.models.discovery import (
    Application, ApplicationEvent, ExternalJobListing, JobPreference, Notification,
    RecommendationCache, Reminder, SavedJob,
)
from app.models.advanced import (
    AdminAuditEvent, EmailSendRecord, GmailConnection, InterviewAnswer,
    InterviewEvaluation, InterviewQuestion, InterviewSession, NotificationPreference,
    OAuthFlow, UserRole,
)


PROJECT = os.environ.get("PHASE4_TEST_PROJECT_ID", "divine-dust-28314320")
BRANCH_NAME = os.environ.get("PHASE4_TEST_BRANCH_NAME", "phase4-full-activation-20261110")
BRANCH_ID = os.environ.get("PHASE4_TEST_BRANCH_ID", "br-round-surf-az9wjgvn")
ORIGINAL = {"users", "profiles", "jobs", "drafts", "recruiter_users", "recruiter_profiles",
            "recruiter_jobs", "recruiter_drafts", "recruiter_sessions", "recruiter_migrations"}
PHASE2 = {"resume_versions", "career_reports", "generation_versions"}
PHASE3 = {"external_job_listings", "saved_jobs", "job_preferences", "applications",
          "application_events", "reminders", "notifications", "recommendation_cache"}
FOUNDATION_MODELS = (ResumeVersion, CareerReport, GenerationVersion, ExternalJobListing,
    SavedJob, JobPreference, Application, ApplicationEvent, Reminder, Notification,
    RecommendationCache)
ADVANCED_MODELS = (InterviewSession, InterviewQuestion, InterviewAnswer, InterviewEvaluation,
    NotificationPreference, GmailConnection, OAuthFlow, EmailSendRecord, UserRole, AdminAuditEvent)
MODELS = FOUNDATION_MODELS + ADVANCED_MODELS
PHASE4 = {model.__tablename__ for model in ADVANCED_MODELS}
REPORT = {"checked_at_utc": datetime.now(timezone.utc).isoformat(), "branch": BRANCH_NAME,
    "branch_id": BRANCH_ID, "schema_only": True, "production_schema_modified": False,
    "production_backup_taken": False,
    "production_activation": "Requires verified backup/restore and explicit production migration approval."}
STAGE = "initialization"


def cli(*args):
    executable = shutil.which("neon.cmd") or shutil.which("neon")
    if not executable:
        raise RuntimeError("CLI unavailable")
    environment = dict(__import__("os").environ); environment["DEBUG"] = ""
    result = subprocess.run([executable, *args, "--project-id", PROJECT, "--output", "json"],
        cwd=ROOT, capture_output=True, text=True, timeout=90, env=environment)
    if result.returncode:
        raise RuntimeError("CLI metadata request failed")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder(); candidates = []
        for index, character in enumerate(result.stdout):
            if character not in '{["':
                continue
            try:
                value, _ = decoder.raw_decode(result.stdout, index)
            except json.JSONDecodeError:
                continue
            if isinstance(value, (dict, list)) or (isinstance(value, str) and value.startswith("postgres")):
                candidates.append(value)
        if not candidates:
            connection_match = re.search(r"postgres(?:ql)?://[^\s\"']+", result.stdout)
            if connection_match:
                return connection_match.group(0)
        if not candidates:
            raise RuntimeError("CLI returned no parseable metadata") from None
        return candidates[-1]


def endpoint(value):
    return (value or "").replace("-pooler.", ".")


def original_metadata(connection):
    inspector = inspect(connection)
    return {name: {"columns": [(c["name"], str(c["type"]), c["nullable"], c["default"])
        for c in inspector.get_columns(name)], "foreign_keys": inspector.get_foreign_keys(name),
        "indexes": inspector.get_indexes(name), "unique": inspector.get_unique_constraints(name),
        "checks": inspector.get_check_constraints(name)} for name in sorted(ORIGINAL)}


def apply_sql(engine, filename):
    sql = (BACKEND / "migrations" / filename).read_text(encoding="utf-8")
    assert not re.search(r"\b(?:DROP\s+TABLE|TRUNCATE|DELETE\s+FROM|ALTER\s+TABLE)\b", sql, re.I)
    # Use SQLAlchemy's explicit autocommit execution mode. Setting ``autocommit``
    # on the pooled connection proxy is driver-dependent and can silently roll
    # DDL back when the proxy is returned to the pool.
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        connection.exec_driver_sql(sql)


def assert_model_metadata(connection):
    inspector = inspect(connection)
    for model in MODELS:
        table = model.__table__
        REPORT["model_check"] = table.name
        REPORT["metadata_step"] = "columns"
        actual = {column["name"]: column for column in inspector.get_columns(table.name)}
        assert set(actual) == set(table.columns.keys())
        for column in table.columns: assert actual[column.name]["nullable"] == column.nullable
        REPORT["metadata_step"] = "unique constraints"
        unique = {tuple(item["column_names"]) for item in inspector.get_unique_constraints(table.name)}
        for constraint in table.constraints:
            if constraint.__class__.__name__ == "UniqueConstraint":
                assert tuple(constraint.columns.keys()) in unique
        REPORT["metadata_step"] = "check constraints"
        checks = {item["name"] for item in inspector.get_check_constraints(table.name)}
        expected_checks = {item.name for item in table.constraints if item.__class__.__name__ == "CheckConstraint"}
        assert expected_checks <= checks
        REPORT["metadata_step"] = "foreign key reflection"
        foreign = {(tuple(item["constrained_columns"]), item["referred_table"], tuple(item["referred_columns"]))
            for item in inspector.get_foreign_keys(table.name)}
        REPORT["metadata_step"] = "foreign key model resolution"
        for constraint in table.foreign_key_constraints:
            expected = (tuple(element.parent.name for element in constraint.elements),
                constraint.elements[0].column.table.name, tuple(element.column.name for element in constraint.elements))
            assert expected in foreign
        REPORT["metadata_step"] = "indexes"
        indexes = {tuple(item["column_names"]) for item in inspector.get_indexes(table.name)}
        assert all(tuple(index.columns.keys()) in indexes for index in table.indexes)


def rejected(db, model):
    failed = False
    try:
        with db.begin_nested(): db.add(model); db.flush()
    except IntegrityError:
        failed = True
    assert failed


def row_counts(connection):
    return {name: connection.execute(text(f'SELECT count(*) FROM public."{name}"')).scalar_one()
            for name in sorted(ORIGINAL | PHASE2 | PHASE3 | PHASE4)}


def synthetic_checks(connection):
    transaction = connection.begin(); db = Session(bind=connection)
    checks = []
    try:
        suffix = uuid4().hex
        first = User(email=f"phase4-{suffix}@example.invalid", hashed_password="not-a-login")
        second = User(email=f"phase4-other-{suffix}@example.invalid", hashed_password="not-a-login")
        db.add_all([first, second]); db.flush()
        profile = Profile(user_id=first.id, full_name="Synthetic", raw_resume_text="Skills: Python", parsed_data={"skills":["Python"]})
        job = Job(user_id=first.id, title="Synthetic", description="Python", extracted_skills={})
        db.add_all([profile, job]); db.flush()
        resume = ResumeVersion(user_id=first.id, profile_id=profile.id, revision=1, fingerprint="a"*64,
            data_json={"skills":["Python"]}, source_text="Skills: Python", source_metadata_json={}, approved=True)
        db.add(resume); db.flush()
        document = GenerationVersion(user_id=first.id, resume_version_id=resume.id, job_id=job.id,
            lineage_id=str(uuid4()), revision=1, kind="email", content_json={"subject_line":"Hi","body":"Body"},
            warnings_json=[], approved=True, model="synthetic")
        db.add(document); db.flush()
        listing = ExternalJobListing(provider="synthetic", provider_job_id=suffix, title="Synthetic", description="Python",
            provider_url="https://example.invalid/job", application_url="https://example.invalid/apply",
            content_fingerprint="b"*64, skills_json=[], normalized_json={})
        db.add(listing); db.flush(); db.add(SavedJob(user_id=first.id, listing_id=listing.id, job_id=job.id, tags_json=[])); db.flush()
        session = InterviewSession(user_id=first.id, job_id=job.id, resume_version_id=resume.id,
            interview_type="technical", difficulty="intermediate", question_count=1,
            prompt_version="v1", rubric_version="v1", model="synthetic", context_hash="c"*64)
        db.add(session); db.flush()
        question = InterviewQuestion(user_id=first.id, session_id=session.id, position=1,
            question_type="technical", question_text="Explain Python", competency="reasoning", rubric_json={"clarity":"Clear"})
        db.add(question); db.flush()
        answer = InterviewAnswer(user_id=first.id, session_id=session.id, question_id=question.id, answer_text="Python answer")
        db.add(answer); db.flush()
        evaluation = InterviewEvaluation(user_id=first.id, session_id=session.id, question_id=question.id,
            answer_id=answer.id, rubric_version="v1", prompt_version="v1", model="synthetic",
            scores_json=[{"category":"clarity","score":80}], evidence_json=["Python"], strengths_json=[],
            improvements_json=[], sample_answer="Possible answer", practice_score=80)
        preference = NotificationPreference(user_id=first.id, categories_json={"interview":True}, timezone="Asia/Calcutta")
        gmail = GmailConnection(user_id=first.id, google_subject="synthetic", encrypted_refresh_token="encrypted", scopes_json=[])
        flow = OAuthFlow(user_id=first.id, provider="gmail", state_hash="d"*64, code_verifier="verifier",
            expires_at=datetime.now(timezone.utc)+timedelta(minutes=5))
        send = EmailSendRecord(user_id=first.id, generation_version_id=document.id, recipient_hash="e"*64,
            subject_hash="f"*64, status="approved", approved_at=datetime.now(timezone.utc), idempotency_key=f"send-{suffix}")
        role = UserRole(user_id=first.id, role="admin")
        audit = AdminAuditEvent(actor_user_id=first.id, action="synthetic", metadata_json={"status":"ok"})
        db.add_all([evaluation, preference, gmail, flow, send, role, audit]); db.flush()
        checks.extend(["interview ownership chain", "rubric evaluation metadata", "notification consent",
            "encrypted-token envelope storage", "send idempotency", "admin role and audit event"])
        rejected(db, InterviewQuestion(user_id=second.id, session_id=session.id, position=2,
            question_type="technical", question_text="Cross owner", competency="test", rubric_json={}))
        rejected(db, EmailSendRecord(user_id=first.id, generation_version_id=document.id,
            recipient_hash="1"*64, subject_hash="2"*64, status="approved", approved_at=datetime.now(timezone.utc),
            idempotency_key=send.idempotency_key))
        rejected(db, InterviewEvaluation(user_id=first.id, session_id=session.id, question_id=question.id,
            answer_id=answer.id, rubric_version="v2", prompt_version="v1", model="synthetic", scores_json=[],
            evidence_json=[], strengths_json=[], improvements_json=[], sample_answer="x", practice_score=101))
        checks.extend(["cross-user question rejected", "duplicate send rejected", "invalid score rejected"])
        return checks
    finally:
        db.close()
        if transaction.is_active: transaction.rollback()


def run():
    global STAGE
    STAGE = "branch metadata lookup"
    branch = cli("branches", "get", BRANCH_ID)
    STAGE = "branch identity assertions"
    assert branch["id"] == BRANCH_ID and branch["name"] == BRANCH_NAME and not branch.get("default")
    assert branch.get("init_source") == "parent-schema"
    STAGE = "development compute lookup"
    dev = cli("postgres", "computes", "list", "--branch", BRANCH_ID)
    STAGE = "production compute lookup"
    prod = cli("postgres", "computes", "list", "--branch", "production")
    production_hosts = {endpoint(item.get("host")) for item in prod} | {endpoint(make_url(settings.DATABASE_URL).host)}
    dev_hosts = {endpoint(item.get("host")) for item in dev}
    assert dev_hosts and not (dev_hosts & production_hosts)
    STAGE = "development connection lookup"
    connection = cli("connection-string", BRANCH_ID, "--database-name", "neondb", "--ssl", "require")
    if isinstance(connection, dict): connection = connection.get("connection_string") or connection.get("uri")
    url = make_url(connection)
    STAGE = "development endpoint assertions"
    assert endpoint(url.host) in dev_hosts and endpoint(url.host) not in production_hosts and "-pooler." not in url.host
    assert url.query.get("sslmode") in {"require", "verify-ca", "verify-full"}
    REPORT.update({"branch_verified": True, "production_endpoint_excluded": True})
    engine = create_engine(url.set(drivername="postgresql+psycopg2"), connect_args={"connect_timeout":20})
    event.listen(engine, "do_connect", resolve_neon_host)
    try:
        STAGE = "development inventory"
        with engine.connect() as conn:
            assert conn.execute(text("SELECT 1")).scalar_one() == 1
            before = original_metadata(conn); present = set(inspect(conn).get_table_names())
            assert ORIGINAL <= present
        for filename, expected, key in (("002_career_intelligence.sql", PHASE2, "phase2"),
                                         ("003_smart_job_discovery.sql", PHASE3, "phase3"),
                                         ("004_advanced_features.sql", PHASE4, "phase4")):
            STAGE = f"{key} development-only migration"
            with engine.connect() as conn: present = set(inspect(conn).get_table_names())
            if not expected <= present:
                assert not (present & expected); apply_sql(engine, filename); REPORT[f"{key}_migration_applied_this_run"] = True
            else: REPORT[f"{key}_migration_applied_this_run"] = False
            with engine.connect() as conn:
                assert expected <= set(inspect(conn).get_table_names())
            REPORT[f"{key}_schema_present"] = True
        STAGE = "metadata and rollback checks"
        with engine.connect() as conn:
            STAGE = "original metadata preservation"
            assert original_metadata(conn) == before
            STAGE = "phase4 model metadata parity"
            assert_model_metadata(conn); conn.rollback()
            STAGE = "pre-synthetic row counts"
            baseline = row_counts(conn); conn.rollback()
            STAGE = "synthetic ownership and rollback checks"
            REPORT["synthetic_checks"] = synthetic_checks(conn)
            STAGE = "post-synthetic row counts"
            assert row_counts(conn) == baseline; conn.rollback()
        REPORT.update({"status":"passed", "select_1":True, "tls_enabled":True,
            "original_tables_preserved":sorted(ORIGINAL), "new_tables_verified":sorted(PHASE2 | PHASE3 | PHASE4),
            "synthetic_rows_rolled_back":True, "new_metadata_matches_models":True})
    finally: engine.dispose()


def write_report():
    (ROOT / "PHASE4_MIGRATION_TEST.md").write_text(
        "# Phase 4 development migration verification\n\nMetadata only. Credential-bearing CLI responses were captured in memory and never written here.\n\n```json\n"+
        json.dumps(REPORT, indent=2)+"\n```\n\nProduction remains unchanged. Production activation requires backup/restore evidence and explicit approval.\n", encoding="utf-8")


if __name__ == "__main__":
    try: run()
    except Exception as error:
        REPORT.update({"status":"failed", "stage":STAGE, "error_type":type(error).__name__,
            "sqlstate":getattr(getattr(error,"orig",error),"pgcode",None)})
        write_report(); print("Development migration verification failed; raw diagnostics withheld."); sys.exit(1)
    write_report(); print("Development migration verification passed; production excluded; synthetic rows rolled back.")
