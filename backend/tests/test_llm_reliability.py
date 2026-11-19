import unittest
from types import SimpleNamespace
from unittest.mock import patch
from google.genai import errors
from pydantic import BaseModel
from app.config import settings
from app.services.llm_client import call_llm, LLMError


class Payload(BaseModel):
    value: str


class GeminiReliabilityTests(unittest.TestCase):
    def test_safe_categories_and_no_permanent_retries(self):
        for code, category in [(400,"request"),(401,"credentials"),(403,"credentials"),(404,"model"),(429,"quota")]:
            with self.subTest(code=code), patch.object(settings,"LLM_API_KEY","synthetic-key"), patch("app.services.llm_client.genai.Client") as factory:
                client=factory.return_value.__enter__.return_value
                client.models.generate_content.side_effect=errors.APIError(code,{"error":{"message":"private-source-marker","code":code}})
                with self.assertRaises(LLMError) as caught:
                    call_llm("synthetic private request")
                self.assertEqual(caught.exception.category,category)
                self.assertNotIn("private-source-marker",str(caught.exception))
                self.assertEqual(client.models.generate_content.call_count,1)

    def test_transient_retry_is_bounded_and_schema_is_sent(self):
        with patch.object(settings,"LLM_API_KEY","synthetic-key"), patch("app.services.llm_client.genai.Client") as factory, patch("app.services.llm_client.time.sleep"):
            client=factory.return_value.__enter__.return_value
            client.models.generate_content.side_effect=[errors.APIError(503,{"error":{"message":"unavailable","code":503}}),SimpleNamespace(text='{"value":"ok"}')]
            self.assertEqual(call_llm("prompt",response_schema=Payload),'{"value":"ok"}')
            self.assertEqual(client.models.generate_content.call_count,2)
            schema=client.models.generate_content.call_args.kwargs["config"].response_json_schema
            self.assertIn("value",schema["properties"])
            self.assertEqual(factory.call_args.kwargs["http_options"].retry_options.attempts,1)

    def test_repeated_transient_error_stops_at_two_attempts(self):
        with patch.object(settings,"LLM_API_KEY","synthetic-key"), patch("app.services.llm_client.genai.Client") as factory, patch("app.services.llm_client.time.sleep"):
            client=factory.return_value.__enter__.return_value
            client.models.generate_content.side_effect=errors.APIError(500,{"error":{"code":500,"message":"private"}})
            with self.assertRaises(LLMError):
                call_llm("prompt")
            self.assertEqual(client.models.generate_content.call_count,2)

    def test_compact_manual_schema_is_sent_without_rewriting(self):
        schema = {"type": "object", "properties": {"value": {"type": "string"}}, "required": ["value"]}
        with patch.object(settings,"LLM_API_KEY","synthetic-key"), patch("app.services.llm_client.genai.Client") as factory:
            client=factory.return_value.__enter__.return_value
            client.models.generate_content.return_value=SimpleNamespace(text='{"value":"ok"}')
            self.assertEqual(call_llm("prompt",response_schema=schema),'{"value":"ok"}')
            sent=client.models.generate_content.call_args.kwargs["config"].response_json_schema
            self.assertIs(sent,schema)

    def test_timeout_is_not_retried(self):
        with patch.object(settings,"LLM_API_KEY","synthetic-key"), patch("app.services.llm_client.genai.Client") as factory:
            client=factory.return_value.__enter__.return_value
            client.models.generate_content.side_effect=TimeoutError("private-marker")
            with self.assertRaises(LLMError) as caught:
                call_llm("prompt")
            self.assertEqual(caught.exception.category,"timeout")
            self.assertNotIn("private-marker",str(caught.exception))
            self.assertEqual(client.models.generate_content.call_count,1)

    def test_installed_http_transport_timeout_is_sanitized(self):
        from importlib import import_module
        for name in ("httpx", "httpx2"):
            try:
                module=import_module(name)
            except ImportError:
                continue
            with self.subTest(transport=name), patch.object(settings,"LLM_API_KEY","synthetic-key"), patch("app.services.llm_client.genai.Client") as factory:
                client=factory.return_value.__enter__.return_value
                client.models.generate_content.side_effect=module.ReadTimeout("private-source-marker")
                with self.assertRaises(LLMError) as caught:
                    call_llm("prompt")
                self.assertEqual(caught.exception.category,"timeout")
                self.assertNotIn("private-source-marker",str(caught.exception))
                self.assertEqual(client.models.generate_content.call_count,1)
