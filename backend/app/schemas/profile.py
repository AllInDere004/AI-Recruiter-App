from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ParsedData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    summary: Optional[str] = None
    skills: List[str] = Field(default_factory=list)
    experience: List[dict] = Field(default_factory=list)
    education: List[dict] = Field(default_factory=list)


class ProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    full_name: Optional[str] = None
    raw_resume_text: str
    parsed_data: Optional[dict] = None
    updated_at: Optional[datetime] = None


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: Optional[str] = None
    parsed_data: Optional[dict] = None
