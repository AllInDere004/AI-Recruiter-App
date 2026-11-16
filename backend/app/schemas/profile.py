from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class EvidenceClaim(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: Optional[str] = None
    field: str = Field(min_length=1, max_length=200)
    value: str = Field(min_length=1, max_length=2000)
    quote: str = Field(max_length=500)
    confidence: Optional[float] = Field(default=None, ge=0, le=1)
    status: Optional[Literal["verified", "uncertain"]] = None


class ExperienceDetail(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    company: Optional[str] = None
    role: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    description: Optional[str] = None
    skills: List[str] = Field(default_factory=list)
    achievements: List[str] = Field(default_factory=list)


class EducationDetail(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    institution: Optional[str] = None
    degree: Optional[str] = None
    field_of_study: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class ProjectDetail(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    name: Optional[str] = None
    description: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    skills: List[str] = Field(default_factory=list)
    achievements: List[str] = Field(default_factory=list)


class ParsedData(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    summary: Optional[str] = None
    skills: List[str] = Field(default_factory=list)
    experience: List[dict] = Field(default_factory=list)
    education: List[dict] = Field(default_factory=list)
    # Optional additions preserve the original seven-field response contract.
    technical_skills: Optional[List[str]] = None
    soft_skills: Optional[List[str]] = None
    certifications: Optional[List[str]] = None
    projects: Optional[List[ProjectDetail]] = None
    internships: Optional[List[ExperienceDetail]] = None
    employment_history: Optional[List[ExperienceDetail]] = None
    education_details: Optional[List[EducationDetail]] = None
    achievements: Optional[List[str]] = None
    evidence: Optional[List[EvidenceClaim]] = None
    uncertain_fields: Optional[List[str]] = None


class ProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    full_name: Optional[str] = None
    raw_resume_text: str
    parsed_data: Optional[dict] = None
    updated_at: Optional[datetime] = None


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    full_name: Optional[str] = None
    parsed_data: Optional[dict] = None
