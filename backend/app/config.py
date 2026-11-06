from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    DATABASE_URL: str
    NEON_DNS_SERVERS: str = ""
    JWT_SECRET_KEY: str = "dev_secret_key"
    LLM_API_KEY: str = Field(
        default="dev_llm_key",
        validation_alias=AliasChoices("LLM_API_KEY", "GEMINI_API_KEY"),
        repr=False,
    )
    LLM_MODEL: str = "gemini-2.5-flash"

    # Later files take priority; process environment variables take precedence.
    model_config = SettingsConfigDict(
        env_file=(PROJECT_DIR / ".env", PROJECT_DIR / ".env.local", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )


settings = Settings()
