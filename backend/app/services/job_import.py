import hashlib
import hmac
import http.client
import ipaddress
import json
import socket
import ssl
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

from app.config import settings


USER_AGENT = "AIRecruiterJobImporter/1.0"
ALLOWED_TYPES = {"text/html", "text/plain", "application/ld+json", "application/json"}


class ImportSecurityError(ValueError):
    pass


class ImportUnavailableError(RuntimeError):
    pass


@dataclass(frozen=True)
class FetchedPage:
    final_url: str
    content_type: str
    body: bytes
    status_code: int
    location: str | None = None


def _is_public(address: str) -> bool:
    value = ipaddress.ip_address(address.split("%", 1)[0])
    return bool(value.is_global and not (
        value.is_private or value.is_loopback or value.is_link_local or value.is_multicast
        or value.is_reserved or value.is_unspecified
    ))


def validate_public_https_url(url: str, resolver=socket.getaddrinfo) -> tuple[str, str, list[str]]:
    value = url.strip()
    parsed = urlsplit(value)
    if parsed.scheme.casefold() != "https" or not parsed.hostname:
        raise ImportSecurityError("Only public HTTPS job URLs are supported.")
    try:
        port = parsed.port
    except ValueError:
        raise ImportSecurityError("The job URL contains an invalid port.") from None
    if parsed.username or parsed.password or port not in {None, 443}:
        raise ImportSecurityError("The job URL contains unsupported credentials or a port.")
    try:
        answers = resolver(parsed.hostname, 443, type=socket.SOCK_STREAM)
    except (socket.gaierror, UnicodeError):
        raise ImportSecurityError("The job URL hostname could not be resolved safely.") from None
    addresses = sorted({answer[4][0] for answer in answers})
    if not addresses or any(not _is_public(address) for address in addresses):
        raise ImportSecurityError("The job URL resolves to a private or restricted network address.")
    normalized = urlunsplit(("https", parsed.hostname.lower(), parsed.path or "/", parsed.query, ""))
    return normalized, parsed.hostname.lower(), addresses


def _pinned_get(url: str, max_bytes: int) -> FetchedPage:
    normalized, hostname, addresses = validate_public_https_url(url)
    parsed = urlsplit(normalized)
    address = addresses[0]
    target = parsed.path or "/"
    if parsed.query:
        target += f"?{parsed.query}"
    tls = None
    try:
        raw = socket.create_connection((address, 443), timeout=settings.JOB_PROVIDER_TIMEOUT_SECONDS)
        tls = ssl.create_default_context().wrap_socket(raw, server_hostname=hostname)
        request = (f"GET {target} HTTP/1.1\r\nHost: {hostname}\r\nUser-Agent: {USER_AGENT}\r\n"
                   "Accept: text/html,text/plain,application/ld+json,application/json\r\nConnection: close\r\n\r\n")
        tls.sendall(request.encode("ascii"))
        response = http.client.HTTPResponse(tls)
        response.begin()
        content_type = response.getheader("content-type", "").split(";", 1)[0].strip().casefold()
        length = response.getheader("content-length")
        if length and int(length) > max_bytes:
            raise ImportSecurityError("The job page is larger than the allowed limit.")
        body = response.read(max_bytes + 1)
        if len(body) > max_bytes:
            raise ImportSecurityError("The job page is larger than the allowed limit.")
        return FetchedPage(normalized, content_type, body, response.status,
                           response.getheader("location"))
    except ImportSecurityError:
        raise
    except (TimeoutError, socket.timeout, ssl.SSLError, OSError, http.client.HTTPException, ValueError):
        raise ImportUnavailableError("The job page could not be retrieved safely. Paste the description instead.") from None
    finally:
        if tls is not None:
            tls.close()


def fetch_public_page(url: str, *, fetch_once=_pinned_get, max_bytes: int | None = None,
                      max_redirects: int = 3) -> FetchedPage:
    limit = max_bytes or settings.JOB_IMPORT_MAX_BYTES
    current = url
    for _ in range(max_redirects + 1):
        validate_public_https_url(current)
        response = fetch_once(current, limit)
        if response.status_code in {301, 302, 303, 307, 308}:
            location = response.location
            if not location:
                raise ImportUnavailableError("The job page redirected without a usable destination.")
            current = urljoin(current, location)
            continue
        if response.status_code < 200 or response.status_code >= 300:
            raise ImportUnavailableError("The job page did not allow retrieval. Paste the description instead.")
        if response.content_type not in ALLOWED_TYPES:
            raise ImportSecurityError("The job URL did not return a supported text document.")
        return response
    raise ImportSecurityError("The job URL redirected too many times.")


class _PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text: list[str] = []
        self.json_scripts: list[str] = []
        self._json = False
        self._json_parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        values = {key.casefold(): value for key, value in attrs}
        if tag.casefold() == "script" and (values.get("type") or "").casefold() == "application/ld+json":
            self._json = True
            self._json_parts = []

    def handle_endtag(self, tag):
        if tag.casefold() == "script" and self._json:
            self.json_scripts.append("".join(self._json_parts))
            self._json = False

    def handle_data(self, data):
        if self._json:
            self._json_parts.append(data)
        elif data.strip():
            self.text.append(data.strip())


def _job_posting(value):
    if isinstance(value, dict):
        if value.get("@type") == "JobPosting" or "JobPosting" in (value.get("@type") or []):
            return value
        for child in value.values():
            found = _job_posting(child)
            if found:
                return found
    if isinstance(value, list):
        for child in value:
            found = _job_posting(child)
            if found:
                return found
    return None


def extract_job_text(page: FetchedPage) -> dict:
    text = page.body.decode("utf-8", errors="replace")
    if page.content_type in {"application/ld+json", "application/json"}:
        try:
            structured = _job_posting(json.loads(text))
        except json.JSONDecodeError:
            structured = None
        plain = text
    elif page.content_type == "text/plain":
        structured, plain = None, text
    else:
        parser = _PageParser()
        parser.feed(text)
        structured = None
        for script in parser.json_scripts:
            try:
                structured = _job_posting(json.loads(script))
            except json.JSONDecodeError:
                continue
            if structured:
                break
        plain = "\n".join(parser.text)
    if structured:
        organization = structured.get("hiringOrganization") or {}
        location = structured.get("jobLocation") or {}
        if isinstance(location, list):
            location = location[0] if location else {}
        address = location.get("address") or {} if isinstance(location, dict) else {}
        description = _PageParser()
        description.feed(str(structured.get("description") or ""))
        body = "\n".join(description.text)
        return {
            "text": body[:100_000], "title": str(structured.get("title") or "")[:500],
            "company": str(organization.get("name") or "")[:500] if isinstance(organization, dict) else "",
            "location": ", ".join(str(address.get(key) or "") for key in ("addressLocality", "addressRegion", "addressCountry") if address.get(key))[:500],
            "application_url": str(structured.get("url") or page.final_url)[:2_000], "structured": True,
        }
    collapsed = "\n".join(line.strip() for line in plain.splitlines() if line.strip())
    if len(collapsed) < 30:
        raise ImportUnavailableError("The job page did not contain enough permitted text. Paste the description instead.")
    return {"text": collapsed[:100_000], "title": "", "company": "", "location": "",
            "application_url": page.final_url, "structured": False}


def robots_allowed(url: str, *, fetch_once=_pinned_get) -> bool:
    parsed = urlsplit(url)
    robots_url = urlunsplit(("https", parsed.hostname or "", "/robots.txt", "", ""))
    try:
        validate_public_https_url(robots_url)
        response = fetch_once(robots_url, 200_000)
    except (ImportSecurityError, ImportUnavailableError):
        return False
    if response.status_code == 404:
        return True
    if response.status_code < 200 or response.status_code >= 300:
        return False
    parser = RobotFileParser()
    parser.set_url(robots_url)
    parser.parse(response.body.decode("utf-8", errors="replace").splitlines())
    return parser.can_fetch(USER_AGENT, url)


def preview_token(user_id: int, source: str) -> str:
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
    payload = f"{int(user_id)}:{digest}"
    signature = hmac.new(settings.JWT_SECRET_KEY.encode("utf-8"), payload.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{payload}:{signature}"


def verify_preview_token(token: str, user_id: int) -> str:
    try:
        owner, digest, signature = token.split(":", 2)
    except ValueError:
        raise ImportSecurityError("The import preview is invalid. Preview the job again.") from None
    payload = f"{owner}:{digest}"
    expected = hmac.new(settings.JWT_SECRET_KEY.encode("utf-8"), payload.encode("ascii"), hashlib.sha256).hexdigest()
    if owner != str(int(user_id)) or not hmac.compare_digest(signature, expected):
        raise ImportSecurityError("The import preview is invalid. Preview the job again.")
    return digest
