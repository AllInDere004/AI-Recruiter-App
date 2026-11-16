"""Production startup safety and additive storage constraint checks."""
import asyncio
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import main
from app.database import Base
from app.models.intelligence import GenerationVersion, ResumeVersion
from app.models.user import User


class Phase2MigrationTests(unittest.TestCase):
    def test_postgresql_startup_never_creates_or_alters_schema(self):
        engine=MagicMock()
        engine.dialect.name="postgresql"
        async def lifespan():
            async with main.lifespan(main.app):
                pass
        with patch.object(main,"engine",engine), patch.object(Base.metadata,"create_all") as create, patch.object(main,"ensure_draft_status_column") as alter:
            asyncio.run(lifespan())
        create.assert_not_called()
        alter.assert_not_called()
        engine.dispose.assert_called_once()

    def test_new_owner_foreign_keys_reject_cross_user_resume_references(self):
        engine=create_engine("sqlite://")
        event.listen(engine,"connect",lambda dbapi,_:dbapi.execute("PRAGMA foreign_keys=ON"))
        Base.metadata.create_all(engine)
        try:
            with Session(engine) as db:
                a=User(email="owner@example.com",hashed_password="unused")
                b=User(email="other@example.com",hashed_password="unused")
                db.add_all([a,b]);db.flush()
                source=ResumeVersion(user_id=a.id,revision=1,fingerprint="a"*64,data_json={},source_text="Example",approved=True)
                db.add(source);db.commit()
                foreign=ResumeVersion(user_id=b.id,parent_id=source.id,revision=1,fingerprint="b"*64,data_json={},source_text="Example",approved=True)
                db.add(foreign)
                with self.assertRaises(IntegrityError):
                    db.commit()
                db.rollback()
        finally:
            engine.dispose()

    def test_reviewed_sql_only_creates_new_phase2_entities(self):
        path=Path(__file__).resolve().parents[1]/"migrations"/"002_career_intelligence.sql"
        sql=path.read_text().upper()
        for forbidden in ["DROP TABLE","TRUNCATE","DELETE FROM","ALTER TABLE","RENAME TO"]:
            self.assertNotIn(forbidden,sql)
        for name in ["RESUME_VERSIONS","CAREER_REPORTS","GENERATION_VERSIONS"]:
            self.assertIn("CREATE TABLE "+name,sql)
