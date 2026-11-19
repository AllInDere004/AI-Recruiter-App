import html
import json
import re
import socket
from datetime import datetime
from html.parser import HTMLParser
from urllib.parse import urlparse
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from app.providers.base import NormalizedJob, ProviderError, SearchPage


class _TextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str):
        if data.strip():
            self.parts.append(data.strip())


def plain_text(value: object, limit: int = 50_000) -> str:
    parser = _TextParser()
    parser.feed(html.unescape(str(value or ""))[:limit])
    return re.sub(r"\s+", " ", " ".join(parser.parts)).strip()


def _https_url(value: object) -> str:
    text = str(value or "").strip()
    parsed = urlparse(text)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ProviderError("The provider returned an unsafe application URL.", status_code=502, retryable=False)
    return text


def _published(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


class JoobleProvider:
    name = "jooble"

    def __init__(self, *, api_key: str, base_url: str, timeout: float = 12.0,
                 requester=None):
        self.api_key = api_key.strip()
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.requester = requester or self._request

    class _NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    def _request(self, payload: dict) -> tuple[int, bytes]:
        request = Request(f"{self.base_url}/{self.api_key}", data=json.dumps(payload).encode("utf-8"),
                          headers={"Accept": "application/json", "Content-Type": "application/json"}, method="POST")
        opener = build_opener(self._NoRedirect())
        try:
            with opener.open(request, timeout=self.timeout) as response:
                return response.status, response.read(2_000_001)
        except HTTPError as error:
            return error.code, error.read(2_000_001)

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def search(self, *, keywords: str, location: str, page: int = 1,
               page_size: int = 20, salary_min: int | None = None,
               job_type: str | None = None, sort: str = "newest") -> SearchPage:
        if not self.configured:
            raise ProviderError("Job discovery is not configured.", status_code=503, retryable=False)
        payload: dict[str, object] = {
            "keywords": keywords.strip(), "location": location.strip(),
            "page": page, "ResultOnPage": page_size, "companysearch": False,
        }
        if salary_min is not None:
            payload["salary"] = salary_min
        try:
            status, body = self.requester(payload)
        except (TimeoutError, socket.timeout, URLError, OSError):
            raise ProviderError("The job provider did not respond in time.") from None
        if status == 403:
            raise ProviderError("The job provider rejected its server credential.", status_code=503, retryable=False)
        if status == 429:
            raise ProviderError("The job provider quota is temporarily exhausted.", status_code=429)
        if status >= 500:
            raise ProviderError("The job provider is temporarily unavailable.")
        if status != 200:
            raise ProviderError("The job provider returned an unexpected response.", status_code=502, retryable=False)
        try:
            if len(body) > 2_000_000:
                raise ValueError("oversized")
            data = json.loads(body.decode("utf-8"))
            rows = data.get("jobs", [])
            total = max(0, int(data.get("totalCount", len(rows))))
        except (ValueError, TypeError, AttributeError):
            raise ProviderError("The job provider returned invalid data.", status_code=502, retryable=False) from None
        jobs: list[NormalizedJob] = []
        seen: set[str] = set()
        for row in rows[:page_size]:
            if not isinstance(row, dict):
                continue
            provider_id = str(row.get("id", "")).strip()
            title = plain_text(row.get("title"), 500)
            link = _https_url(row.get("link"))
            if not provider_id or not title or provider_id in seen:
                continue
            seen.add(provider_id)
            jobs.append(NormalizedJob(
                provider=self.name, provider_job_id=provider_id, title=title,
                company=plain_text(row.get("company"), 500) or None,
                location=plain_text(row.get("location"), 500) or None,
                job_type=plain_text(row.get("type"), 100) or None,
                salary_text=plain_text(row.get("salary"), 500) or None,
                experience_text=None, skills=[], description=plain_text(row.get("snippet")),
                published_at=_published(row.get("updated")), provider_url=link,
                application_url=link,
                normalized={"source": plain_text(row.get("source"), 200) or "Jooble"},
            ))
        return SearchPage(jobs=jobs, total=total, page=page, page_size=page_size, provider=self.name)
