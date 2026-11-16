"""Disabled-by-default Gmail OAuth and explicit approved-draft delivery."""
import base64
import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException
from sqlalchemy import inspect
from sqlalchemy.exc import SQLAlchemyError

from app.config import settings
from app.models.advanced import GmailConnection, OAuthFlow


GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"
OPENID_SCOPES = "openid email"


def schema_ready(db):
    try:
        tables = set(inspect(db.connection()).get_table_names())
        return {"gmail_connections", "oauth_flows", "email_send_records"}.issubset(tables)
    except SQLAlchemyError:
        db.rollback()
        return False


def configured():
    return bool(settings.ENABLE_GMAIL and settings.GOOGLE_CLIENT_ID.strip() and
                settings.GOOGLE_CLIENT_SECRET.strip() and settings.GOOGLE_OAUTH_REDIRECT_URI.strip() and
                settings.GMAIL_TOKEN_ENCRYPTION_KEY.strip())


def require_configured(db):
    if not schema_ready(db) or not configured():
        raise HTTPException(503, "Gmail integration is disabled or not configured.")


def _fernet():
    try:
        return Fernet(settings.GMAIL_TOKEN_ENCRYPTION_KEY.encode())
    except (ValueError, TypeError):
        raise HTTPException(503, "Gmail token encryption is not configured correctly.") from None


def encrypt_token(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt_token(value: str) -> str:
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken:
        raise HTTPException(503, "The Gmail connection must be reconnected.") from None


def start_oauth(db, user_id: int):
    require_configured(db)
    state = secrets.token_urlsafe(48)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    db.add(OAuthFlow(user_id=user_id, provider="gmail", state_hash=hashlib.sha256(state.encode()).hexdigest(),
                     code_verifier=verifier,
                     expires_at=datetime.now(timezone.utc) + timedelta(minutes=settings.OAUTH_STATE_TTL_MINUTES)))
    db.commit()
    query = urlencode({"client_id": settings.GOOGLE_CLIENT_ID, "redirect_uri": settings.GOOGLE_OAUTH_REDIRECT_URI,
        "response_type": "code", "scope": f"{OPENID_SCOPES} {GMAIL_SEND_SCOPE}", "access_type": "offline",
        "prompt": "consent", "state": state, "code_challenge": challenge, "code_challenge_method": "S256"})
    return f"https://accounts.google.com/o/oauth2/v2/auth?{query}"


def _request_json(request: Request):
    try:
        with urlopen(request, timeout=15) as response:
            return json.loads(response.read(1_000_000))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
        raise HTTPException(502, "Google OAuth or Gmail could not complete the request.") from None


def exchange_code(code: str, verifier: str):
    data = urlencode({"code": code, "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET, "redirect_uri": settings.GOOGLE_OAUTH_REDIRECT_URI,
        "grant_type": "authorization_code", "code_verifier": verifier}).encode()
    return _request_json(Request("https://oauth2.googleapis.com/token", data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST"))


def google_identity(access_token: str):
    return _request_json(Request("https://openidconnect.googleapis.com/v1/userinfo",
        headers={"Authorization": f"Bearer {access_token}"}))


def finish_oauth(db, state: str, code: str, *, exchanger=exchange_code, identity_fetcher=google_identity):
    require_configured(db)
    now = datetime.now(timezone.utc)
    digest = hashlib.sha256(state.encode()).hexdigest()
    flow = db.query(OAuthFlow).filter(OAuthFlow.state_hash == digest, OAuthFlow.provider == "gmail").with_for_update().first()
    if flow is None or flow.consumed_at is not None or flow.expires_at.replace(tzinfo=flow.expires_at.tzinfo or timezone.utc) <= now:
        raise HTTPException(400, "OAuth state is invalid or expired.")
    flow.consumed_at = now
    token = exchanger(code, flow.code_verifier)
    access = token.get("access_token")
    if not isinstance(access, str) or not access:
        raise HTTPException(502, "Google OAuth did not return an access token.")
    identity = identity_fetcher(access)
    subject, email = identity.get("sub"), identity.get("email")
    if not isinstance(subject, str) or not subject:
        raise HTTPException(502, "Google OAuth identity could not be verified.")
    value = db.query(GmailConnection).filter(GmailConnection.user_id == flow.user_id).with_for_update().first()
    refresh = token.get("refresh_token")
    if value is None and (not isinstance(refresh, str) or not refresh):
        raise HTTPException(502, "Google did not grant offline access. Reconnect and approve access.")
    if value is None:
        value = GmailConnection(user_id=flow.user_id, google_subject=subject,
            encrypted_refresh_token=encrypt_token(refresh), scopes_json=[])
        db.add(value)
    elif isinstance(refresh, str) and refresh:
        value.encrypted_refresh_token = encrypt_token(refresh)
    value.google_subject = subject
    value.email_hint = email if isinstance(email, str) else None
    value.scopes_json = str(token.get("scope", f"{OPENID_SCOPES} {GMAIL_SEND_SCOPE}")).split()
    value.token_expires_at = now + timedelta(seconds=max(60, int(token.get("expires_in", 3600))))
    value.revoked_at = None
    db.commit(); db.refresh(value)
    return value


def refresh_access(connection: GmailConnection):
    data = urlencode({"client_id": settings.GOOGLE_CLIENT_ID, "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "refresh_token": decrypt_token(connection.encrypted_refresh_token), "grant_type": "refresh_token"}).encode()
    value = _request_json(Request("https://oauth2.googleapis.com/token", data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST"))
    token = value.get("access_token")
    if not isinstance(token, str) or not token:
        raise HTTPException(502, "Google did not refresh the Gmail connection.")
    return token


def send_message(connection: GmailConnection, recipient: str, subject: str, body: str, *, sender=_request_json):
    access = refresh_access(connection)
    message = EmailMessage(); message["To"] = recipient; message["Subject"] = subject
    if connection.email_hint:
        message["From"] = connection.email_hint
    message.set_content(body)
    raw = base64.urlsafe_b64encode(message.as_bytes()).rstrip(b"=").decode()
    return sender(Request("https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
        data=json.dumps({"raw": raw}).encode(), headers={"Authorization": f"Bearer {access}",
        "Content-Type": "application/json"}, method="POST"))
