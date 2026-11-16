"""Verify migrations 002-004 on an isolated child of production.

Connection credentials are captured in memory from the Neon CLI and are never
printed or persisted. This script refuses the default branch and the configured
production endpoint before executing any DDL.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import make_url

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))

from app.config import settings
from app.database import resolve_neon_host


PROJECT_ID = "divine-dust-28314320"
PRODUCTION_BRANCH_ID = "br-summer-bread-az2p9coe"
BRANCH_ID = os.environ.get("PRODUCTION_REHEARSAL_BRANCH_ID", "br-lucky-moon-azq5607n")
BRANCH_NAME = os.environ.get(
    "PRODUCTION_REHEARSAL_BRANCH_NAME", "production-migration-rehearsal-20261110"
)
ORIGINAL = {
    "drafts", "jobs", "profiles", "recruiter_drafts", "recruiter_jobs",
    "recruiter_migrations", "recruiter_profiles", "recruiter_sessions",
    "recruiter_users", "users",
}
PHASE2 = {"resume_versions", "career_reports", "generation_versions"}
PHASE3 = {
    "external_job_listings", "saved_jobs", "job_preferences", "applications",
    "application_events", "reminders", "notifications", "recommendation_cache",
}
PHASE4 = {
    "interview_sessions", "interview_questions", "interview_answers",
    "interview_evaluations", "notification_preferences", "gmail_connections",
    "oauth_flows", "email_send_records", "user_roles", "admin_audit_events",
}
MIGRATIONS = (
    ("002_career_intelligence.sql", PHASE2),
    ("003_smart_job_discovery.sql", PHASE3),
    ("004_advanced_features.sql", PHASE4),
)


def cli(*args: str):
    executable = shutil.which("neon.cmd") or shutil.which("neon")
    if not executable:
        raise RuntimeError("Neon CLI unavailable")
    environment = dict(os.environ)
    environment["DEBUG"] = ""
    result = subprocess.run(
        [executable, *args, "--project-id", PROJECT_ID, "--output", "json"],
        cwd=ROOT, capture_output=True, text=True, timeout=90, env=environment,
    )
    if result.returncode:
        raise RuntimeError("Neon CLI metadata request failed")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        candidates = []
        for index, character in enumerate(result.stdout):
            if character not in '{[\"':
                continue
            try:
                value, _ = decoder.raw_decode(result.stdout, index)
            except json.JSONDecodeError:
                continue
            if isinstance(value, (dict, list)) or (
                isinstance(value, str) and value.startswith("postgres")
            ):
                candidates.append(value)
        if not candidates:
            connection_match = re.search(r"postgres(?:ql)?://[^\s\"']+", result.stdout)
            if connection_match:
                return connection_match.group(0)
        if not candidates:
            raise RuntimeError("Neon CLI returned no parseable metadata") from None
        return candidates[-1]


def endpoint(host: str | None) -> str:
    return (host or "").replace("-pooler.", ".")


def table_metadata(connection, names: set[str]):
    inspector = inspect(connection)
    return {
        name: {
            "columns": [(c["name"], str(c["type"]), c["nullable"], c["default"])
                        for c in inspector.get_columns(name)],
            "foreign_keys": inspector.get_foreign_keys(name),
            "indexes": inspector.get_indexes(name),
            "unique": inspector.get_unique_constraints(name),
            "checks": inspector.get_check_constraints(name),
        }
        for name in sorted(names)
    }


def row_counts(connection, names: set[str]):
    return {
        name: connection.execute(text(f'SELECT count(*) FROM public."{name}"')).scalar_one()
        for name in sorted(names)
    }


def apply_migration(engine, filename: str) -> float:
    sql = (BACKEND / "migrations" / filename).read_text(encoding="utf-8")
    if re.search(r"\b(?:DROP\s+TABLE|TRUNCATE|DELETE\s+FROM|ALTER\s+TABLE|UPDATE\s+)\b", sql, re.I):
        raise RuntimeError(f"Non-additive statement found in {filename}")
    started = time.monotonic()
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        connection.exec_driver_sql(sql)
    return round(time.monotonic() - started, 3)


def main() -> int:
    branch = cli("branches", "get", BRANCH_ID)
    if branch.get("default") or branch["id"] == PRODUCTION_BRANCH_ID:
        raise RuntimeError("Refusing to run against the default/production branch")
    if branch.get("parent_id") != PRODUCTION_BRANCH_ID or branch.get("init_source") != "parent-data":
        raise RuntimeError("Rehearsal branch is not a data clone of production")

    computes = cli("postgres", "computes", "list", "--branch", BRANCH_ID)
    rehearsal_hosts = {endpoint(item.get("host")) for item in computes}
    production_host = endpoint(make_url(settings.DATABASE_URL).host)
    if not rehearsal_hosts or production_host in rehearsal_hosts:
        raise RuntimeError("Production endpoint exclusion failed")

    connection_string = cli(
        "connection-string", BRANCH_ID, "--database-name", "neondb", "--ssl", "require"
    )
    if isinstance(connection_string, dict):
        connection_string = connection_string.get("connection_string") or connection_string.get("uri")
    url = make_url(connection_string)
    if endpoint(url.host) not in rehearsal_hosts or endpoint(url.host) == production_host:
        raise RuntimeError("Credential endpoint does not match the rehearsal branch")
    if "-pooler." in (url.host or "") or url.query.get("sslmode") not in {"require", "verify-ca", "verify-full"}:
        raise RuntimeError("Migrations require a direct TLS connection")

    engine = create_engine(url.set(drivername="postgresql+psycopg2"), connect_args={"connect_timeout": 20})
    event.listen(engine, "do_connect", resolve_neon_host)
    report = {
        "branch": BRANCH_NAME,
        "branch_id": BRANCH_ID,
        "parent_branch_id": PRODUCTION_BRANCH_ID,
        "parent_lsn": branch.get("parent_lsn"),
        "parent_timestamp": branch.get("parent_timestamp"),
        "expires_at": branch.get("expires_at"),
        "production_modified": False,
    }
    try:
        with engine.connect() as connection:
            if connection.execute(text("SELECT 1")).scalar_one() != 1:
                raise RuntimeError("SELECT 1 failed")
            before_tables = set(inspect(connection).get_table_names())
            if not ORIGINAL <= before_tables or (PHASE2 | PHASE3 | PHASE4) & before_tables:
                raise RuntimeError("Unexpected rehearsal baseline schema")
            before_metadata = table_metadata(connection, ORIGINAL)
            before_counts = row_counts(connection, ORIGINAL)
            history_before = connection.execute(
                text("SELECT name FROM recruiter_migrations ORDER BY applied_at, name")
            ).scalars().all()

        timings = {}
        for filename, expected in MIGRATIONS:
            timings[filename] = apply_migration(engine, filename)
            with engine.connect() as connection:
                if not expected <= set(inspect(connection).get_table_names()):
                    raise RuntimeError(f"Missing tables after {filename}")

        with engine.connect() as connection:
            after_tables = set(inspect(connection).get_table_names())
            after_counts = row_counts(connection, ORIGINAL)
            new_counts = row_counts(connection, PHASE2 | PHASE3 | PHASE4)
            history_after = connection.execute(
                text("SELECT name FROM recruiter_migrations ORDER BY applied_at, name")
            ).scalars().all()
            if table_metadata(connection, ORIGINAL) != before_metadata:
                raise RuntimeError("Original table metadata changed")
            if after_counts != before_counts:
                raise RuntimeError("Original table row counts changed")
            if any(new_counts.values()):
                raise RuntimeError("New tables were not empty after migration")
            expected_tables = ORIGINAL | PHASE2 | PHASE3 | PHASE4
            if not expected_tables <= after_tables:
                raise RuntimeError("Expected migrated schema is incomplete")
            ownership_constraints = connection.execute(text("""
                SELECT count(*) FROM information_schema.table_constraints
                WHERE constraint_schema='public' AND constraint_type='FOREIGN KEY'
                  AND constraint_name IN (
                    'fk_resume_versions_parent_owner','fk_career_reports_resume_owner',
                    'fk_generation_versions_parent_owner','fk_generation_versions_resume_owner',
                    'fk_applications_saved_owner','fk_applications_resume_owner',
                    'fk_applications_email_owner','fk_applications_cover_owner',
                    'fk_application_events_owner','fk_reminders_application_owner',
                    'fk_notifications_reminder_owner','fk_recommendation_resume_owner',
                    'fk_interview_sessions_resume_owner','fk_interview_questions_session_owner',
                    'fk_interview_questions_followup_owner','fk_interview_answers_session_owner',
                    'fk_interview_answers_question_owner','fk_interview_evaluations_session_owner',
                    'fk_interview_evaluations_question_owner','fk_interview_evaluations_answer_owner',
                    'fk_email_send_generation_owner'
                  )
            """)).scalar_one()
            index_count = connection.execute(text("""
                SELECT count(*) FROM pg_indexes WHERE schemaname='public'
                  AND tablename = ANY(:tables)
            """), {"tables": sorted(PHASE2 | PHASE3 | PHASE4)}).scalar_one()

        report.update({
            "status": "passed",
            "select_1": True,
            "direct_tls_connection": True,
            "production_endpoint_excluded": True,
            "original_table_count": len(ORIGINAL),
            "new_table_count": len(PHASE2 | PHASE3 | PHASE4),
            "original_row_counts_preserved": before_counts == after_counts,
            "original_metadata_preserved": True,
            "new_tables_empty": True,
            "ownership_foreign_keys_verified": ownership_constraints,
            "new_table_indexes_verified": index_count,
            "migration_history_unchanged": history_before == history_after,
            "recorded_migrations": history_after,
            "migration_seconds": timings,
        })
    finally:
        engine.dispose()

    (ROOT / "PRODUCTION_MIGRATION_REHEARSAL.md").write_text(
        "# Production-like migration rehearsal\n\n"
        "Credential-safe verification on an isolated child of production. Production was not modified.\n\n"
        "```json\n" + json.dumps(report, indent=2) + "\n```\n",
        encoding="utf-8",
    )
    print("Production-like migration rehearsal passed; production endpoint excluded.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        message = re.sub(r"postgres(?:ql)?://[^\s]+", "[database-url-redacted]", str(error))
        print(f"Rehearsal failed safely: {type(error).__name__}: {message}", file=sys.stderr)
        raise SystemExit(1)
