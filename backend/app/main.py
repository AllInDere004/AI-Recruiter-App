from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import Base, engine, get_db
from app.config import settings
from app.migrations import ensure_draft_status_column
from app.api import auth, drafts, email, jobs, match, profile, resume, intelligence, discovery, applications, interviews, notifications, integrations, analytics, admin
import app.models.user
import app.models.profile
import app.models.job
import app.models.draft
import app.models.intelligence
import app.models.discovery
import app.models.advanced


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.validate_runtime()
    # Production schemas are managed by reviewed, explicit migrations only.
    # Isolated SQLite fixtures retain automatic initialization for local tests.
    if engine.dialect.name == "sqlite":
        Base.metadata.create_all(bind=engine)
        ensure_draft_status_column(engine)
    try:
        yield
    finally:
        engine.dispose()


app = FastAPI(title="AI Recruiter API", lifespan=lifespan)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers.setdefault("Cache-Control", "no-store" if request.url.path.startswith("/api/") else "no-cache")
    if settings.FORCE_HTTPS:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.exception_handler(RequestValidationError)
async def invalid_request(request, error):
    # Pydantic's default errors include raw input (passwords, resumes, tokens).
    messages = {
        "missing": "Field required.", "extra_forbidden": "Unexpected field.",
        "string_type": "Expected text.", "string_too_short": "Text is too short.",
        "string_too_long": "Text is too long.", "int_type": "Expected an integer.",
        "int_parsing": "Expected an integer.", "float_type": "Expected a number.",
        "float_parsing": "Expected a number.", "bool_type": "Expected true or false.",
        "bool_parsing": "Expected true or false.", "json_invalid": "Invalid JSON body.",
        "literal_error": "Choose one of the supported values.",
    }
    details = []
    for item in error.errors():
        kind = item.get("type", "invalid")
        # Locations can contain arbitrary client-provided dictionary keys.
        location = item.get("loc", ())
        origin = location[0] if location and location[0] in {"body", "query", "path", "header", "cookie"} else "body"
        details.append({"loc": [origin], "msg": messages.get(kind, "Invalid value."), "type": kind})
    return JSONResponse(status_code=422, content={"detail": details})


@app.exception_handler(SQLAlchemyError)
async def database_unavailable(request, error):
    # Driver exceptions can contain SQL parameters and private candidate text.
    if isinstance(error, IntegrityError):
        return JSONResponse(status_code=409, content={"detail": "This record changed concurrently. Refresh and retry."})
    return JSONResponse(status_code=503, content={"detail": "The database request could not be completed. Please retry."})

app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(resume.router)
app.include_router(profile.router)
app.include_router(jobs.router)
app.include_router(match.router)
app.include_router(email.router)
app.include_router(drafts.router)
app.include_router(intelligence.router)
app.include_router(discovery.router)
app.include_router(applications.router)
app.include_router(interviews.router)
app.include_router(notifications.router)
app.include_router(integrations.router)
app.include_router(analytics.router)
app.include_router(admin.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
if settings.allowed_hosts:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
if settings.FORCE_HTTPS:
    app.add_middleware(HTTPSRedirectMiddleware)


@app.get("/")
def read_root():
    return {"message": "AI Recruiter API is running", "docs": "/docs"}


@app.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok", "message": "Database connected successfully"}


@app.get("/live")
def liveness():
    return {"status": "ok"}


@app.get("/ready")
def readiness(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ready"}
