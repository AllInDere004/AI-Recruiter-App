"""Environment loading regression checks using synthetic credentials only."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from app.config import Settings


class SettingsTests(unittest.TestCase):
    def load(self, **values):
        with patch.dict(os.environ, {}, clear=True):
            return Settings(_env_file=None, DATABASE_URL="sqlite://", **values)

    def test_accepts_both_key_names(self):
        for name in ("LLM_API_KEY", "GEMINI_API_KEY"):
            with self.subTest(name=name):
                with patch.dict(os.environ, {name: "synthetic-key"}, clear=True):
                    config = Settings(_env_file=None, DATABASE_URL="sqlite://")
                self.assertTrue(config.LLM_API_KEY == "synthetic-key")

    def test_legacy_name_wins_in_same_source(self):
        config = self.load(LLM_API_KEY="legacy-test", GEMINI_API_KEY="gemini-test")
        self.assertTrue(config.LLM_API_KEY == "legacy-test")

    def test_key_is_hidden_from_settings_repr(self):
        self.assertNotIn("synthetic-key", repr(self.load(GEMINI_API_KEY="synthetic-key")))

    def test_dotenv_alias_is_loaded_outside_working_directory(self):
        with TemporaryDirectory() as directory:
            env = Path(directory) / ".env"
            env.write_text("DATABASE_URL=sqlite://\nGEMINI_API_KEY=file-test\n", encoding="utf-8")
            with patch.dict(os.environ, {}, clear=True):
                config = Settings(_env_file=env)
            self.assertTrue(config.LLM_API_KEY == "file-test")

    def test_environment_overrides_dotenv_even_with_different_alias(self):
        with TemporaryDirectory() as directory:
            env = Path(directory) / ".env"
            env.write_text("DATABASE_URL=sqlite://\nLLM_API_KEY=file-test\n", encoding="utf-8")
            with patch.dict(os.environ, {"GEMINI_API_KEY": "runtime-test"}, clear=True):
                config = Settings(_env_file=env)
            self.assertTrue(config.LLM_API_KEY == "runtime-test")
