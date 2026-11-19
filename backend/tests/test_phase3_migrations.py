from pathlib import Path
import unittest


class Phase3MigrationTests(unittest.TestCase):
    def test_reviewed_sql_is_additive_and_contains_all_entities(self):
        path = Path(__file__).resolve().parents[1] / "migrations" / "003_smart_job_discovery.sql"
        sql = path.read_text().upper()
        for forbidden in ["DROP TABLE", "TRUNCATE", "DELETE FROM", "ALTER TABLE", "RENAME TO"]:
            self.assertNotIn(forbidden, sql)
        for name in ["EXTERNAL_JOB_LISTINGS", "SAVED_JOBS", "JOB_PREFERENCES", "APPLICATIONS",
                     "APPLICATION_EVENTS", "REMINDERS", "NOTIFICATIONS", "RECOMMENDATION_CACHE"]:
            self.assertIn("CREATE TABLE " + name, sql)
        self.assertIn("FK_APPLICATIONS_SAVED_OWNER", sql)
        self.assertIn("UQ_EXTERNAL_JOBS_PROVIDER_ID", sql)
        self.assertIn("IX_REMINDERS_DUE_CLAIM", sql)
