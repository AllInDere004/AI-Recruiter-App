from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    ENVIRONMENT: Literal["development", "test", "staging", "production"] = "development"
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"
    ALLOWED_HOSTS: str = "localhost,127.0.0.1,testserver"
    FORCE_HTTPS: bool = False
    DATABASE_URL: str = Field(repr=False)
    NEON_DNS_SERVERS: str = ""
    JWT_SECRET_KEY: str = Field(default="development_only_secret_key_32_bytes", repr=False)
    LLM_API_KEY: str = Field(
        default="dev_llm_key",
        validation_alias=AliasChoices("LLM_API_KEY", "GEMINI_API_KEY"),
        repr=False,
    )
    LLM_MODEL: str = "gemini-2.5-flash"
    # New persistence stays unavailable until its additive migration is reviewed.
    ENABLE_CAREER_INTELLIGENCE: bool = False
    CAREER_AI_REQUESTS_PER_MINUTE: int = Field(default=6, ge=1, le=60)
    AI_REQUESTS_PER_MINUTE: int = Field(default=30, ge=1, le=120)
    # Phase 3 remains unavailable until its additive migration is reviewed.
    ENABLE_JOB_DISCOVERY: bool = False
    JOB_PROVIDER: str = "himalayas"
    HIMALAYAS_API_KEY: str = Field(default="", repr=False)
    HIMALAYAS_API_BASE_URL: str = "https://himalayas.app/jobs/api"
    # Legacy adapter remains available for existing deployments.
    JOOBLE_API_KEY: str = Field(default="", repr=False)
    JOOBLE_API_BASE_URL: str = "https://in.jooble.org/api"
    JOB_SEARCH_REQUESTS_PER_MINUTE: int = Field(default=10, ge=1, le=60)
    JOB_IMPORT_REQUESTS_PER_MINUTE: int = Field(default=5, ge=1, le=30)
    JOB_PROVIDER_TIMEOUT_SECONDS: float = Field(default=12.0, ge=2.0, le=30.0)
    JOB_IMPORT_MAX_BYTES: int = Field(default=2_000_000, ge=100_000, le=5_000_000)
    REMINDER_WORKER_TOKEN: str = Field(default="", repr=False)
    # Phase 4 remains opt-in until migration 004 is approved for an environment.
    ENABLE_ADVANCED_FEATURES: bool = False
    INTERVIEW_AI_REQUESTS_PER_MINUTE: int = Field(default=4, ge=1, le=30)
    INTERVIEW_MAX_ANSWER_CHARS: int = Field(default=20_000, ge=1_000, le=100_000)
    ENABLE_GMAIL: bool = False
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = Field(default="", repr=False)
    GOOGLE_OAUTH_REDIRECT_URI: str = ""
    GMAIL_TOKEN_ENCRYPTION_KEY: str = Field(default="", repr=False)
    OAUTH_STATE_TTL_MINUTES: int = Field(default=10, ge=5, le=30)

    @property
    def cors_origins(self) -> list[str]:
        return [value.strip() for value in self.CORS_ORIGINS.split(",") if value.strip()]

    @property
    def allowed_hosts(self) -> list[str]:
        return [value.strip() for value in self.ALLOWED_HOSTS.split(",") if value.strip()]

    def validate_runtime(self) -> None:
        """Reject unsafe production combinations without including secret values."""
        if self.ENVIRONMENT != "production":
            return
        problems = []
        if len(self.JWT_SECRET_KEY.encode("utf-8")) < 32 or self.JWT_SECRET_KEY.startswith("development_only"):
            problems.append("JWT_SECRET_KEY must be a unique value of at least 32 bytes")
        if not self.FORCE_HTTPS:
            problems.append("FORCE_HTTPS must be enabled")
        if not self.cors_origins or "*" in self.cors_origins or any(not origin.startswith("https://") for origin in self.cors_origins):
            problems.append("CORS_ORIGINS must contain explicit HTTPS origins")
        if not self.allowed_hosts or "*" in self.allowed_hosts:
            problems.append("ALLOWED_HOSTS must contain explicit hosts")
        if not self.DATABASE_URL.startswith(("postgres://", "postgresql://")):
            problems.append("DATABASE_URL must use PostgreSQL")
        if self.ENABLE_GMAIL and not all((self.GOOGLE_CLIENT_ID, self.GOOGLE_CLIENT_SECRET,
                                          self.GOOGLE_OAUTH_REDIRECT_URI, self.GMAIL_TOKEN_ENCRYPTION_KEY)):
            problems.append("Gmail integration is enabled without complete OAuth encryption settings")
        if problems:
            raise RuntimeError("Unsafe production configuration: " + "; ".join(problems))

    # Later files take priority; process environment variables take precedence.
    model_config = SettingsConfigDict(
        env_file=(PROJECT_DIR / ".env", PROJECT_DIR / ".env.local", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )


settings = Settings()
