import json
import socket
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from app.providers.base import NormalizedJob, ProviderError, SearchPage
from app.providers.jooble import _https_url, plain_text


HIMALAYAS_SOURCE_URL = "https://himalayas.app"
EMPLOYMENT_TYPES = {
    "full time": "Full Time", "full-time": "Full Time", "part time": "Part Time",
    "part-time": "Part Time", "contract": "Contractor", "contractor": "Contractor",
    "temporary": "Temporary", "intern": "Intern", "internship": "Intern",
    "volunteer": "Volunteer", "other": "Other",
}


def _timestamp(value: object) -> datetime | None:
    try:
        number = int(value)
        return datetime.fromtimestamp(number, tz=timezone.utc) if number > 0 else None
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def _locations(value: object) -> str:
    if not isinstance(value, list) or not value:
        return "Worldwide"
    names = []
    for item in value:
        name = plain_text(item.get("name"), 100) if isinstance(item, dict) else plain_text(item, 100)
        if name and name.casefold() not in {existing.casefold() for existing in names}:
            names.append(name)
    return ", ".join(names[:20]) or "Remote"


def _salary(row: dict) -> str | None:
    minimum, maximum = row.get("minSalary"), row.get("maxSalary")
    if not isinstance(minimum, (int, float)) and not isinstance(maximum, (int, float)):
        return None
    currency = plain_text(row.get("currency"), 10) or ""
    period = plain_text(row.get("salaryPeriod"), 20) or "annual"
    if isinstance(minimum, (int, float)) and isinstance(maximum, (int, float)):
        amount = f"{minimum:,.0f}-{maximum:,.0f}"
    else:
        amount = f"{(minimum if isinstance(minimum, (int, float)) else maximum):,.0f}"
    return f"{currency} {amount} / {period}".strip()


class HimalayasProvider:
    name = "himalayas"

    def __init__(self, *, api_key: str, base_url: str, timeout: float = 12.0,
                 requester=None):
        self.api_key = api_key.strip()
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.requester = requester or self._request

    class _NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    @property
    def configured(self) -> bool:
        # Himalayas permits anonymous access, but this app requires its configured
        # server key so users do not depend on a shared public allowance.
        return bool(self.api_key)

    def _request(self, params: dict) -> tuple[int, bytes, dict[str, str]]:
        headers = {"Accept": "application/json", "User-Agent": "AI-Recruiter-App/1.0"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = Request(f"{self.base_url}/search?{urlencode(params)}", headers=headers, method="GET")
        opener = build_opener(self._NoRedirect())
        try:
            with opener.open(request, timeout=self.timeout) as response:
                return response.status, response.read(5_000_001), dict(response.headers.items())
        except HTTPError as error:
            return error.code, error.read(5_000_001), dict(error.headers.items())

    def search(self, *, keywords: str, location: str, page: int = 1,
               page_size: int = 20, salary_min: int | None = None,
               job_type: str | None = None, sort: str = "newest") -> SearchPage:
        if not self.configured:
            raise ProviderError("Himalayas job discovery is not configured.", status_code=503, retryable=False)
        params: dict[str, object] = {"q": keywords.strip(), "page": page,
                                     "sort": "recent" if sort == "newest" else "relevant"}
        if location.strip():
            params["country"] = location.strip()
        if job_type and job_type.strip():
            normalized_type = EMPLOYMENT_TYPES.get(job_type.strip().casefold())
            if normalized_type:
                params["employment_type"] = normalized_type
        try:
            status, body, headers = self.requester(params)
        except (TimeoutError, socket.timeout, URLError, OSError):
            raise ProviderError("The Himalayas job provider did not respond in time.") from None
        if status == 401:
            raise ProviderError("Himalayas rejected its server credential.", status_code=503, retryable=False)
        if status == 429:
            try:
                retry_after = max(1, min(int(headers.get("Retry-After", "60")), 3600))
            except (TypeError, ValueError):
                retry_after = 60
            raise ProviderError("The Himalayas request limit is temporarily exhausted.", status_code=429,
                                retry_after=retry_after)
        if status == 400:
            raise ProviderError("Himalayas did not accept one or more search filters.", status_code=422,
                                retryable=False)
        if status >= 500:
            raise ProviderError("Himalayas job search is temporarily unavailable.")
        if status != 200:
            raise ProviderError("Himalayas returned an unexpected response.", status_code=502, retryable=False)
        try:
            if len(body) > 5_000_000:
                raise ValueError("oversized")
            data = json.loads(body.decode("utf-8"))
            rows = data.get("jobs", [])
            if not isinstance(rows, list):
                raise TypeError("jobs")
            total = max(0, int(data.get("totalCount", len(rows))))
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError, AttributeError):
            raise ProviderError("Himalayas returned invalid data.", status_code=502, retryable=False) from None

        jobs: list[NormalizedJob] = []
        seen: set[str] = set()
        now = datetime.now(timezone.utc)
        for row in rows:
            if not isinstance(row, dict):
                continue
            provider_id = plain_text(row.get("guid"), 255)
            title = plain_text(row.get("title"), 500)
            expires_at = _timestamp(row.get("expiryDate"))
            if not provider_id or not title or provider_id in seen or (expires_at and expires_at <= now):
                continue
            application_url = _https_url(row.get("applicationLink"))
            maximum = row.get("maxSalary")
            if salary_min is not None and isinstance(maximum, (int, float)) and maximum < salary_min:
                continue
            seen.add(provider_id)
            categories = row.get("categories") if isinstance(row.get("categories"), list) else []
            parents = row.get("parentCategories") if isinstance(row.get("parentCategories"), list) else []
            skills = []
            for value in categories + parents:
                skill = plain_text(value, 100)
                if skill and skill.casefold() not in {existing.casefold() for existing in skills}:
                    skills.append(skill)
            seniority = row.get("seniority") if isinstance(row.get("seniority"), list) else []
            description = plain_text(row.get("description"), 100_000) or plain_text(row.get("excerpt"), 10_000)
            if not description:
                continue
            jobs.append(NormalizedJob(
                provider=self.name, provider_job_id=provider_id, title=title,
                company=plain_text(row.get("companyName"), 500) or None,
                location=_locations(row.get("locationRestrictions")),
                job_type=plain_text(row.get("employmentType"), 100) or None,
                salary_text=_salary(row),
                experience_text=", ".join(plain_text(value, 100) for value in seniority if plain_text(value, 100)) or None,
                skills=skills[:100], description=description,
                published_at=_timestamp(row.get("pubDate")), expires_at=expires_at,
                provider_url=HIMALAYAS_SOURCE_URL, application_url=application_url,
                normalized={"source": "Himalayas", "company_slug": plain_text(row.get("companySlug"), 200),
                            "timezone_restrictions": row.get("timezoneRestrictions", []),
                            "expiry_date": row.get("expiryDate")},
            ))
            if len(jobs) >= min(max(page_size, 1), 20):
                break
        return SearchPage(jobs=jobs, total=total, page=page,
                          page_size=min(max(page_size, 1), 20), provider=self.name)
