import json
import unittest
from unittest.mock import patch

from app.services.hallucination_check import verify_email_facts
from app.services.llm_client import LLMResponseError


class FactVerificationTests(unittest.TestCase):
    def test_returns_specific_unverified_claim_warnings(self):
        warnings = [" Unverified claim: increased revenue 50%. ", "Unverified claim: increased revenue 50%."]
        with patch("app.services.hallucination_check.call_llm", return_value=json.dumps({"warnings": warnings})) as llm:
            result = verify_email_facts("Built Python APIs", "I increased revenue 50%.")
            self.assertEqual(result, ["Unverified claim: increased revenue 50%."])
            prompt = llm.call_args.args[0]
            self.assertIn("Built Python APIs", prompt)
            self.assertIn("I increased revenue 50%.", prompt)
            self.assertIn("prospective employer", prompt)
            self.assertTrue(llm.call_args.kwargs["json_mode"])

    def test_verified_facts_return_empty_warnings(self):
        with patch("app.services.hallucination_check.call_llm", return_value='{"warnings": []}'):
            self.assertEqual(verify_email_facts("Python developer", "I develop with Python."), [])

    def test_malformed_fact_check_never_counts_as_verified(self):
        for response in ['{}', '{"warnings": "verified"}', '{"warnings": [1]}', 'not JSON']:
            with patch("app.services.hallucination_check.call_llm", return_value=response):
                with self.assertRaises(LLMResponseError):
                    verify_email_facts("Resume", "Email")
        with self.assertRaises(ValueError):
            verify_email_facts("", "Email")
