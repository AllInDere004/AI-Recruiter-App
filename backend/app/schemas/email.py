from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EmailGenerateRequest(BaseModel):
    job_id: int = Field(gt=0)
    situation: str = Field(min_length=1, max_length=100)
    tone: str = Field(min_length=1, max_length=100)
    custom_notes: Optional[str] = None

    @field_validator("situation", "tone")
    @classmethod
    def nonblank_choice(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Value cannot be blank.")
        return value.strip()


class EmailGenerateResponse(BaseModel):
    draft_id: int
    subject_line: str
    body: str
    match_score: float = Field(ge=0, le=100)
    hallucination_warnings: List[str]


class DraftResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    job_id: int
    situation: str
    tone: str
    status: Literal["Draft", "Sent", "Replied", "Interview", "Rejected"] = "Draft"
    subject_line: Optional[str] = None
    body: str
    match_score: Optional[float] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


class DraftUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_line: Optional[str] = None
    body: Optional[str] = None
    situation: Optional[str] = None
    tone: Optional[str] = None
    status: Optional[Literal["Draft", "Sent", "Replied", "Interview", "Rejected"]] = None

    @field_validator("body", "situation", "tone", "status")
    @classmethod
    def supplied_value_is_not_blank(cls, value: Optional[str]) -> str:
        if value is None or not value.strip():
            raise ValueError("Provided body, situation, and tone values cannot be null or blank.")
        return value
