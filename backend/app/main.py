from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import Base, engine, get_db
from app.migrations import ensure_draft_status_column
from app.api import auth, drafts, email, jobs, match, profile, resume
import app.models.user
import app.models.profile
import app.models.job
import app.models.draft


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    ensure_draft_status_column(engine)
    try:
        yield
    finally:
        engine.dispose()


app = FastAPI(title="AI Recruiter API", lifespan=lifespan)

app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(resume.router)
app.include_router(profile.router)
app.include_router(jobs.router)
app.include_router(match.router)
app.include_router(email.router)
app.include_router(drafts.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"message": "AI Recruiter API is running", "docs": "/docs"}


@app.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok", "message": "Database connected successfully"}
