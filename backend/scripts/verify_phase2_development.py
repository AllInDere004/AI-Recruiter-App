"""Apply/test the reviewed migration ONLY on the explicitly authorized dev branch.

Neon credentials and connection strings stay in memory and are never printed.
No production connection is opened by this script. Synthetic row checks roll back.
"""
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from uuid import uuid4

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))

from sqlalchemy import create_engine, event, func, inspect, select, text
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


PROJECT = "divine-dust-28314320"
BRANCH_NAME = "phase2-career-intelligence-20261106"
BRANCH_ID = "br-jolly-boat-az77y9f1"
ORIGINAL = {"users", "profiles", "jobs", "drafts", "recruiter_users", "recruiter_profiles",
            "recruiter_jobs", "recruiter_drafts", "recruiter_sessions", "recruiter_migrations"}
MODELS = (ResumeVersion, CareerReport, GenerationVersion)
NEW = {model.__tablename__ for model in MODELS}
REPORT = {"checked_at_utc": datetime.now(timezone.utc).isoformat(), "branch": BRANCH_NAME,
          "branch_id": BRANCH_ID, "production_schema_modified": False,
          "production_backup_taken": False,
          "production_activation": "Requires verified backup and explicit user approval."}
STAGE = "initialization"


def cli(*args):
    executable = shutil.which("neon.cmd") or shutil.which("neon")
    if not executable:
        raise RuntimeError("CLI unavailable")
    result = subprocess.run([executable, *args, "--project-id", PROJECT, "--output", "json"],
                            cwd=ROOT, capture_output=True, text=True, timeout=60)
    if result.returncode:
        # Never include stdout/stderr: CLI output can contain credentials.
        raise RuntimeError("CLI metadata request failed")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return result.stdout.strip()


def endpoint(value):
    return (value or "").replace("-pooler.", ".")


def existing_metadata(connection):
    inspector = inspect(connection)
    result = {}
    for name in sorted(ORIGINAL):
        result[name] = {
            "columns": [(c["name"], str(c["type"]), c["nullable"], c["default"]) for c in inspector.get_columns(name)],
            "foreign_keys": inspector.get_foreign_keys(name),
            "indexes": inspector.get_indexes(name),
            "unique": inspector.get_unique_constraints(name),
            "checks": inspector.get_check_constraints(name),
        }
    return result


def counts(connection):
    return {name: connection.execute(text('SELECT count(*) FROM public."'+name+'"')).scalar_one()
            for name in sorted(ORIGINAL | NEW)}


def assert_new_metadata(connection):
    inspector = inspect(connection)
    for model in MODELS:
        table = model.__table__
        actual = {column["name"]: column for column in inspector.get_columns(table.name)}
        assert set(actual) == set(table.columns.keys())
        for column in table.columns:
            assert actual[column.name]["nullable"] == column.nullable
        unique = {tuple(c["column_names"]) for c in inspector.get_unique_constraints(table.name)}
        for constraint in table.constraints:
            if constraint.__class__.__name__ == "UniqueConstraint":
                assert tuple(constraint.columns.keys()) in unique
        checks = {c["name"] for c in inspector.get_check_constraints(table.name)}
        expected_checks = {c.name for c in table.constraints if c.__class__.__name__ == "CheckConstraint"}
        assert expected_checks <= checks
        foreign = {(tuple(f["constrained_columns"]), f["referred_table"], tuple(f["referred_columns"]))
                   for f in inspector.get_foreign_keys(table.name)}
        for constraint in table.foreign_key_constraints:
            expected = (tuple(e.parent.name for e in constraint.elements),
                        constraint.elements[0].column.table.name,
                        tuple(e.column.name for e in constraint.elements))
            assert expected in foreign
        indexes = {tuple(i["column_names"]) for i in inspector.get_indexes(table.name)}
        assert all(tuple(index.columns.keys()) in indexes for index in table.indexes)


def check_synthetic_rows(connection):
    transaction = connection.begin()
    db = Session(bind=connection)
    checks = []
    try:
        suffix = uuid4().hex
        first = User(email=f"synthetic-{suffix}@example.invalid", hashed_password="not-a-login")
        second = User(email=f"synthetic-other-{suffix}@example.invalid", hashed_password="not-a-login")
        db.add_all([first, second]); db.flush()
        profile = Profile(user_id=first.id, full_name="Synthetic", raw_resume_text="Synthetic Python", parsed_data={"skills": ["Python"]})
        job = Job(user_id=first.id, title="Synthetic", description="Python", extracted_skills={"required_skills": ["Python"]})
        db.add_all([profile, job]); db.flush()
        resume = ResumeVersion(user_id=first.id, profile_id=profile.id, revision=1,
            fingerprint="a"*64, data_json={"skills":["Python"]}, source_text="Synthetic Python",
            source_metadata_json={"synthetic":True}, approved=True)
        db.add(resume); db.flush()
        report = CareerReport(user_id=first.id, resume_version_id=resume.id, job_id=job.id,
            kind="match", algorithm_version="synthetic-v1", profile_version="a"*64,
            job_version="b"*64, input_hash="c"*64, result_json={"overall_score":100})
        original = GenerationVersion(user_id=first.id, resume_version_id=resume.id, job_id=job.id,
            lineage_id=str(uuid4()), revision=1, kind="email", content_json={"body":"Synthetic Python"},
            warnings_json=[], approved=False, model="synthetic-model")
        db.add_all([report, original]); db.flush()
        assert db.get(CareerReport,report.id).result_json["overall_score"] == 100
        checks.append("synthetic report and generation persistence")
        child = GenerationVersion(user_id=first.id, resume_version_id=resume.id, job_id=job.id,
            lineage_id=original.lineage_id, revision=2, parent_id=original.id, kind="email",
            content_json={"body":"Synthetic revised Python"},warnings_json=[],approved=False,model="synthetic-model")
        db.add(child); db.flush()
        assert original.content_json["body"] == "Synthetic Python"
        checks.append("immutable generation parent and child history")
        for model, values in [
            (ResumeVersion, dict(user_id=second.id, parent_id=resume.id, revision=1, fingerprint="d"*64,
                                data_json={},source_text="Synthetic",approved=False)),
            (CareerReport, dict(user_id=second.id,resume_version_id=resume.id,job_id=job.id,
                                kind="ats",algorithm_version="synthetic-v1",profile_version="d"*64,
                                job_version="e"*64,input_hash="f"*64,result_json={})),
            (GenerationVersion,dict(user_id=first.id,resume_version_id=resume.id,job_id=job.id,
                                    lineage_id=original.lineage_id,revision=3,parent_id=original.id,kind="email",
                                    content_json={"body":"stale"},warnings_json=[],approved=False,model="synthetic-model")),
        ]:
            rejected = False
            try:
                with db.begin_nested():
                    db.add(model(**values)); db.flush()
            except IntegrityError:
                rejected = True
            assert rejected
        checks.extend(["cross-user resume parent rejected", "cross-user report source rejected", "stale sibling revision rejected"])
        return checks
    finally:
        db.close()
        if transaction.is_active:
            transaction.rollback()


def run():
    global STAGE
    STAGE = "branch identity verification"
    branch = cli("branches", "get", BRANCH_ID)
    assert isinstance(branch,dict)
    assert branch["id"] == BRANCH_ID and branch["name"] == BRANCH_NAME
    assert branch.get("project_id") == PROJECT
    assert not branch.get("default") and not branch.get("primary")
    assert branch["name"] != "production"
    dev_computes = cli("postgres", "computes", "list", "--branch", BRANCH_ID)
    prod_computes = cli("postgres", "computes", "list", "--branch", "production")
    production_hosts = {endpoint(x.get("host")) for x in prod_computes}
    production_hosts.add(endpoint(make_url(settings.DATABASE_URL).host))
    expected_hosts = {endpoint(x.get("host")) for x in dev_computes}
    assert expected_hosts and not (expected_hosts & production_hosts)
    connection = cli("connection-string", BRANCH_ID, "--database-name", "neondb", "--ssl", "require")
    if isinstance(connection,dict):
        connection = connection.get("connection_string") or connection.get("connection_uri") or connection.get("uri")
    assert isinstance(connection,str)
    url = make_url(connection)
    assert endpoint(url.host) in expected_hosts and endpoint(url.host) not in production_hosts
    assert url.database == "neondb" and "-pooler." not in url.host
    assert url.query.get("sslmode") in {"require", "verify-ca", "verify-full"}
    REPORT["branch_verified"] = True
    REPORT["production_endpoint_excluded"] = True
    engine = create_engine(url.set(drivername="postgresql+psycopg2"),connect_args={"connect_timeout":20})
    event.listen(engine,"do_connect",resolve_neon_host)
    try:
        STAGE = "development schema inventory"
        with engine.connect() as conn:
            assert conn.execute(text("SELECT 1")).scalar_one() == 1
            assert conn.execute(text("SELECT current_database()")).scalar_one() == "neondb"
            assert conn.connection.driver_connection.info.ssl_in_use
            before = existing_metadata(conn)
            present = set(inspect(conn).get_table_names())
            assert ORIGINAL <= present
        STAGE = "development-only migration"
        if not (present & NEW):
            sql = (BACKEND/"migrations"/"002_career_intelligence.sql").read_text()
            assert not re.search(r"\b(?:DROP\s+TABLE|TRUNCATE|DELETE\s+FROM|ALTER\s+TABLE)\b",sql,re.I)
            raw = engine.raw_connection()
            try:
                raw.autocommit = True
                with raw.cursor() as cursor:
                    cursor.execute(sql)
            finally:
                raw.close()
            REPORT["migration_applied"] = True
        else:
            assert NEW <= present
            REPORT["migration_applied"] = False
            REPORT["already_applied"] = True
        STAGE = "schema constraints and original preservation"
        with engine.connect() as conn:
            assert existing_metadata(conn) == before
            assert_new_metadata(conn)
            conn.rollback()
            baseline_counts = counts(conn)
            conn.rollback()
            STAGE = "synthetic rollback tests"
            REPORT["synthetic_checks"] = check_synthetic_rows(conn)
            assert counts(conn) == baseline_counts
            conn.rollback()
        REPORT.update({"status":"passed","select_1":True,"tls_enabled":True,
                       "original_tables_preserved":sorted(ORIGINAL),"new_tables_verified":sorted(NEW),
                       "synthetic_rows_rolled_back":True,"new_metadata_matches_models":True})
    finally:
        engine.dispose()


def write_report():
    path = ROOT/"PHASE2_MIGRATION_TEST.md"
    path.write_text("# Phase 2 development migration verification\n\n"
                    "This report contains metadata only. Credentials and connection strings were never printed.\n\n"
                    "```json\n"+json.dumps(REPORT,indent=2)+"\n```\n\n"
                    "Production schema activation remains disabled. A verified production backup and explicit user approval are required before any production migration.\n",
                    encoding="utf-8")


if __name__ == "__main__":
    try:
        run()
    except Exception as error:
        REPORT.update({"status":"failed","stage":STAGE,"error_type":type(error).__name__,
                       "sqlstate":getattr(getattr(error,"orig",error),"pgcode",None)})
        write_report()
        print("Development migration verification failed at",STAGE,"; type:",type(error).__name__,"; raw diagnostics withheld.")
        sys.exit(1)
    write_report()
    print("Development migration verification passed; original tables preserved; synthetic tests rolled back. Report: PHASE2_MIGRATION_TEST.md")
