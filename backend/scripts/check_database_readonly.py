"""Credential-safe, read-only database connectivity diagnostic."""

from __future__ import annotations

import sys

from sqlalchemy import text
from sqlalchemy.engine import make_url

from app.config import settings
from app.database import engine


def main() -> int:
    configured_url = make_url(settings.DATABASE_URL)
    ssl_mode = configured_url.query.get("sslmode", "not-set")

    print(f"URL_CONFIGURED={bool(configured_url.host and configured_url.database)}")
    print(f"NEON_HOST={bool(configured_url.host and configured_url.host.endswith('.neon.tech'))}")
    print(f"POOLED_HOST={bool(configured_url.host and '-pooler.' in configured_url.host)}")
    print(f"SSL_MODE={ssl_mode}")

    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                connection.execute(text("SET TRANSACTION READ ONLY"))
                select_one = connection.execute(text("SELECT 1")).scalar_one()
                database_name = connection.execute(text("SELECT current_database()")).scalar_one()
                tables = connection.execute(
                    text(
                        "SELECT tablename FROM pg_catalog.pg_tables "
                        "WHERE schemaname = 'public' ORDER BY tablename"
                    )
                ).scalars().all()
            finally:
                transaction.rollback()
    except Exception as exc:  # pragma: no cover - diagnostic path
        print(f"CONNECTION_ERROR_TYPE={type(exc).__name__}", file=sys.stderr)
        print(f"CONNECTION_ERROR={exc}", file=sys.stderr)
        return 1

    print(f"SELECT_1={select_one}")
    print(f"DATABASE={database_name}")
    print(f"TABLE_COUNT={len(tables)}")
    print(f"TABLES={','.join(tables)}")
    print(f"PHASE2_PRESENT={'candidate_profiles' in tables}")
    print(f"PHASE3_PRESENT={'applications' in tables}")
    print(f"DISCOVERY_ENABLED={settings.ENABLE_JOB_DISCOVERY}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
