from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class JobCreate(BaseModel):
    title: Optional[str] = None
    company: Optional[str] = None
    description: str = Field(min_length=1)

    @field_validator("description")
    @classmethod
    def description_is_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Job description cannot be blank.")
        return value


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    title: Optional[str] = None
    company: Optional[str] = None
    description: str
    extracted_skills: Optional[dict] = None
    created_at: datetime


class MatchRequest(BaseModel):
    job_id: int = Field(gt=0)


class MatchResponse(BaseModel):
    overall_score: float = Field(ge=0, le=100)
    matched_skills: List[str]
    missing_skills: List[str]
    summary: str
