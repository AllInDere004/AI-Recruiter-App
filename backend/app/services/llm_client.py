import json
import re

from google import genai
from google.genai import errors, types

from app.config import settings


class LLMError(RuntimeError):
    pass


class LLMConfigurationError(LLMError):
    pass


class LLMResponseError(LLMError):
    pass


def call_llm(prompt: str, system_message: str = "", *, json_mode: bool = False) -> str:
    api_key = settings.LLM_API_KEY.strip()
    if not api_key or api_key == "dev_llm_key":
        raise LLMConfigurationError(
            "Set LLM_API_KEY or GEMINI_API_KEY in backend/.env to your Google Gemini API key, "
            "then restart the backend."
        )
    if not settings.LLM_MODEL.strip():
        raise LLMConfigurationError("Set LLM_MODEL in backend/.env to a Gemini model name.")
    config = types.GenerateContentConfig(
        system_instruction=system_message or None,
        response_mime_type="application/json" if json_mode else "text/plain",
    )
    try:
        with genai.Client(api_key=api_key, http_options=types.HttpOptions(api_version="v1beta", timeout=45000)) as client:
            response = client.models.generate_content(model=settings.LLM_MODEL, contents=prompt, config=config)
            text = response.text
    except errors.APIError:
        raise LLMError("Google Gemini could not complete the request. Check your API key, model access, and quota.") from None
    except (TimeoutError, ConnectionError):
        raise LLMError("The Google Gemini request timed out or could not connect.") from None
    except Exception:
        # Do not expose upstream payloads, resume contents, or API credentials.
        raise LLMError("The Google Gemini request failed. Please try again.") from None
    if not text or not text.strip():
        raise LLMResponseError("Google Gemini returned no text. The request may have been blocked.")
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
        raise LLMResponseError("Google Gemini returned invalid JSON.") from None
    if not isinstance(parsed, dict):
        raise LLMResponseError("Google Gemini must return a JSON object.")
    return parsed
