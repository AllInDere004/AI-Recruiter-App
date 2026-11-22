import json
import re
import time
from importlib import import_module

from google import genai
from google.genai import errors, types
from pydantic import BaseModel

from app.config import settings


class LLMError(RuntimeError):
    """Sanitized upstream error; never attach provider payloads or request content."""

    def __init__(self, message: str, *, category: str = "provider", provider_status: int | None = None):
        super().__init__(message)
        self.category = category
        self.provider_status = provider_status


class LLMConfigurationError(LLMError):
    pass


class LLMResponseError(LLMError):
    pass


# Support the installed SDK's HTTP transport without adding dependencies.
_transport_errors = [TimeoutError, ConnectionError]
for _transport_name in ("httpx", "httpx2"):
    try:
        _transport = import_module(_transport_name)
        for _error_name in ("TimeoutException", "NetworkError"):
            _error_type = getattr(_transport, _error_name, None)
            if isinstance(_error_type, type):
                _transport_errors.append(_error_type)
    except ImportError:
        pass
TRANSPORT_ERRORS = tuple(_transport_errors)

# No model fallback. Two total attempts only for transient upstream failures.
MAX_ATTEMPTS = 2
TRANSIENT_CODES = {500, 502, 503, 504}
PROVIDER_MESSAGES = {
    400: ("request", "Google Gemini rejected the request. Check the configured model and request options."),
    401: ("credentials", "Google Gemini rejected the API credentials. Check the server-side API key."),
    403: ("credentials", "Google Gemini denied access. Check the server-side key and model permissions."),
    404: ("model", "The configured Gemini model is unavailable. Choose a model available to your account."),
    429: ("quota", "Google Gemini rate or quota limit reached. Wait before retrying and check your allowance."),
}


def call_llm(prompt: str, system_message: str = "", *, json_mode: bool = False,
             response_schema: type[BaseModel] | dict | None = None) -> str:
    api_key = settings.LLM_API_KEY.strip()
    if not api_key or api_key == "dev_llm_key":
        raise LLMConfigurationError(
            "Set LLM_API_KEY or GEMINI_API_KEY in backend/.env to your Google Gemini API key, "
            "then restart the backend.", category="configuration"
        )
    model = settings.LLM_MODEL.strip()
    if not model:
        raise LLMConfigurationError("Set LLM_MODEL in backend/.env to a Gemini model name.", category="configuration")
    provider_schema = response_schema if isinstance(response_schema, dict) else (
        response_schema.model_json_schema() if response_schema else None
    )
    config = types.GenerateContentConfig(
        system_instruction=system_message or None,
        response_mime_type="application/json" if json_mode or response_schema else "text/plain",
        # JSON Schema avoids SDK conversion failures for strict object schemas.
        response_json_schema=provider_schema,
    )
    # Disable SDK retries so upstream retry logging cannot include sensitive payloads.
    options = types.HttpOptions(
        api_version="v1beta", timeout=45000,
        retry_options=types.HttpRetryOptions(attempts=1),
    )
    for attempt in range(MAX_ATTEMPTS):
        try:
            with genai.Client(api_key=api_key, http_options=options) as client:
                response = client.models.generate_content(model=model, contents=prompt, config=config)
                text = response.text
            break
        except errors.APIError as error:
            code = error.code
            if code in TRANSIENT_CODES and attempt + 1 < MAX_ATTEMPTS:
                time.sleep(0.25)
                continue
            category, message = PROVIDER_MESSAGES.get(
                code, ("transient" if code in TRANSIENT_CODES else "provider",
                       "Google Gemini is temporarily unavailable. Please try again later.")
            )
            raise LLMError(message, category=category, provider_status=code) from None
        except TRANSPORT_ERRORS:
            # A timeout may have completed upstream: avoid a second potentially charged generation.
            raise LLMError("The Google Gemini request timed out or could not connect.", category="timeout") from None
        except Exception:
            raise LLMError("The Google Gemini request failed. Please try again.", category="transport") from None
    if not text or not text.strip():
        raise LLMResponseError("Google Gemini returned no text. The request may have been blocked.", category="response")
    return text.strip()


def extract_json(text: str) -> dict:
    """Read a JSON object, including fenced JSON or JSON surrounded by prose."""
    value = text.strip()
    fence = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", value, flags=re.DOTALL | re.IGNORECASE)
    if fence:
        value = fence.group(1)
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        for match in re.finditer(r"\{", value):
            try:
                parsed, _ = decoder.raw_decode(value, match.start())
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
        raise LLMResponseError("Google Gemini returned invalid JSON.", category="response") from None
    if not isinstance(parsed, dict):
        raise LLMResponseError("Google Gemini must return a JSON object.", category="response")
    return parsed
