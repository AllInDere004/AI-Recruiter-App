import unittest
from sqlalchemy import create_engine, text
from app.migrations import ensure_draft_status_column


class TrackerMigrationTests(unittest.TestCase):
    def test_existing_rows_are_preserved_and_migration_is_idempotent(self):
        engine = create_engine("sqlite://")
        try:
            with engine.begin() as connection:
                connection.execute(text("CREATE TABLE drafts (id INTEGER PRIMARY KEY, body VARCHAR NOT NULL)"))
                connection.execute(text("INSERT INTO drafts (id,body) VALUES (1,'Existing draft')"))
            ensure_draft_status_column(engine)
            ensure_draft_status_column(engine)
            with engine.connect() as connection:
                row = connection.execute(text("SELECT body,status FROM drafts WHERE id=1")).one()
                self.assertEqual(tuple(row),("Existing draft","Draft"))
        finally:
            engine.dispose()
