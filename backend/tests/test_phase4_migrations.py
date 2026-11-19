from pathlib import Path
import unittest


class Phase4MigrationTests(unittest.TestCase):
    def test_reviewed_sql_is_additive_and_contains_all_entities(self):
        path = Path(__file__).resolve().parents[1] / "migrations" / "004_advanced_features.sql"
        sql = path.read_text(encoding="utf-8").upper()
        for forbidden in ("DROP TABLE", "TRUNCATE", "DELETE FROM", "ALTER TABLE", "RENAME TO"):
            self.assertNotIn(forbidden, sql)
        self.assertEqual(sql.count("BEGIN;"), 1)
        self.assertEqual(sql.count("COMMIT;"), 1)
        for table in (
            "INTERVIEW_SESSIONS", "INTERVIEW_QUESTIONS", "INTERVIEW_ANSWERS",
            "INTERVIEW_EVALUATIONS", "NOTIFICATION_PREFERENCES", "GMAIL_CONNECTIONS",
            "OAUTH_FLOWS", "EMAIL_SEND_RECORDS", "USER_ROLES", "ADMIN_AUDIT_EVENTS",
        ):
            self.assertIn(f"CREATE TABLE {table}", sql)
        self.assertIn("FK_INTERVIEW_QUESTIONS_SESSION_OWNER", sql)
        self.assertIn("FK_EMAIL_SEND_GENERATION_OWNER", sql)
        self.assertIn("CHECK (PRACTICE_SCORE BETWEEN 0 AND 100)", sql)
