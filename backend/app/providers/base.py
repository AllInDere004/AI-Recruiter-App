from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Protocol


class ProviderError(RuntimeError):
    """Safe provider failure whose message never contains credentials or payloads."""

    def __init__(self, message: str, *, status_code: int = 503, retryable: bool = True,
                 retry_after: int | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable
        self.retry_after = retry_after


@dataclass(frozen=True)
class NormalizedJob:
    provider: str
    provider_job_id: str
    title: str
    company: str | None
    location: str | None
    job_type: str | None
    salary_text: str | None
    experience_text: str | None
    skills: list[str]
    description: str
    published_at: datetime | None
    provider_url: str
    application_url: str
    expires_at: datetime | None = None
    normalized: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class SearchPage:
    jobs: list[NormalizedJob]
    total: int
    page: int
    page_size: int
    provider: str


class JobProvider(Protocol):
    name: str

    def search(self, *, keywords: str, location: str, page: int = 1,
               page_size: int = 20, salary_min: int | None = None,
               job_type: str | None = None, sort: str = "newest") -> SearchPage: ...
