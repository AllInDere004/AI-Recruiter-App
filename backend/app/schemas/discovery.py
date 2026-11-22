from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ListingResponse(StrictModel):
    id: int
    provider: str
    provider_job_id: str
    title: str
    company: str | None
    location: str | None
    job_type: str | None
    salary_text: str | None
    experience_text: str | None
    skills: list[str]
    description: str
    provider_url: str
    application_url: str
    published_at: datetime | None
    fetched_at: datetime
    freshness: Literal["today", "recent", "older", "unknown"]
    saved_job_id: int | None = None


class SearchResponse(StrictModel):
    jobs: list[ListingResponse]
    total: int
    page: int
    page_size: int
    provider: str
    partial: bool = False


class SaveJobRequest(StrictModel):
    listing_id: int = Field(gt=0)
    notes: str | None = Field(default=None, max_length=10_000)
    tags: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("tags")
    @classmethod
    def clean_tags(cls, value: list[str]) -> list[str]:
        result: list[str] = []
        for item in value:
            tag = item.strip()
            if not tag or len(tag) > 50:
                raise ValueError("Tags must be 1 to 50 characters.")
            if tag.casefold() not in {existing.casefold() for existing in result}:
                result.append(tag)
        return result


class SavedJobUpdate(StrictModel):
    notes: str | None = Field(default=None, max_length=10_000)
    tags: list[str] | None = Field(default=None, max_length=20)
    archived: bool | None = None

    @field_validator("tags")
    @classmethod
    def clean_optional_tags(cls, value: list[str] | None) -> list[str] | None:
        return SaveJobRequest.clean_tags(value) if value is not None else value


class SavedJobResponse(StrictModel):
    id: int
    listing: ListingResponse
    job_id: int | None
    notes: str | None
    tags: list[str]
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime | None


class PreferenceUpdate(StrictModel):
    roles: list[str] = Field(default_factory=list, max_length=20)
    locations: list[str] = Field(default_factory=list, max_length=20)
    remote_policy: Literal["any", "remote", "hybrid", "onsite"] = "any"
    experience_levels: list[str] = Field(default_factory=list, max_length=10)
    job_types: list[str] = Field(default_factory=list, max_length=10)
    timezone: str = Field(default="Asia/Calcutta", min_length=1, max_length=100)

    @field_validator("roles", "locations", "experience_levels", "job_types")
    @classmethod
    def clean_lists(cls, value: list[str]) -> list[str]:
        result = []
        for raw in value:
            item = raw.strip()
            if not item or len(item) > 100:
                raise ValueError("Preference values must be 1 to 100 characters.")
            if item.casefold() not in {existing.casefold() for existing in result}:
                result.append(item)
        return result


class PreferenceResponse(PreferenceUpdate):
    id: int
    version: int
    updated_at: datetime


class ImportPreviewRequest(StrictModel):
    url: str | None = Field(default=None, max_length=2_000)
    manual_text: str | None = Field(default=None, max_length=100_000)

    @model_validator(mode="after")
    def has_source(self):
        if not (self.url and self.url.strip()) and not (self.manual_text and self.manual_text.strip()):
            raise ValueError("Provide a job URL or pasted job description.")
        return self


class ImportSaveRequest(StrictModel):
    preview_token: str = Field(min_length=20, max_length=500)
    title: str = Field(min_length=1, max_length=500)
    company: str | None = Field(default=None, max_length=500)
    location: str | None = Field(default=None, max_length=500)
    job_type: str | None = Field(default=None, max_length=100)
    salary_text: str | None = Field(default=None, max_length=500)
    experience_text: str | None = Field(default=None, max_length=500)
    skills: list[str] = Field(default_factory=list, max_length=100)
    description: str = Field(min_length=1, max_length=100_000)
    application_url: str = Field(min_length=1, max_length=2_000)
    notes: str | None = Field(default=None, max_length=10_000)
    tags: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("tags")
    @classmethod
    def clean_import_tags(cls, value: list[str]) -> list[str]:
        return SaveJobRequest.clean_tags(value)


ApplicationState = Literal["Saved", "Preparing", "Applied", "Assessment", "Interview", "Offer", "Rejected", "Withdrawn"]


class ApplicationCreate(StrictModel):
    saved_job_id: int = Field(gt=0)
    notes: str | None = Field(default=None, max_length=20_000)


class ApplicationUpdate(StrictModel):
    expected_version: int = Field(gt=0)
    status: ApplicationState | None = None
    confirm_submission: bool = False
    application_date: datetime | None = None
    recruiter_name: str | None = Field(default=None, max_length=500)
    recruiter_email: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=20_000)
    interview_at: datetime | None = None
    deadline_at: datetime | None = None
    resume_version_id: int | None = Field(default=None, gt=0)
    email_version_id: int | None = Field(default=None, gt=0)
    cover_letter_version_id: int | None = Field(default=None, gt=0)


class ReminderCreate(StrictModel):
    application_id: int | None = Field(default=None, gt=0)
    kind: Literal["application", "interview", "deadline", "follow_up"]
    title: str = Field(min_length=1, max_length=500)
    note: str | None = Field(default=None, max_length=10_000)
    due_at: datetime
    timezone: str = Field(min_length=1, max_length=100)


class ReminderUpdate(StrictModel):
    expected_version: int = Field(gt=0)
    action: Literal["complete", "snooze", "dismiss"]
    snoozed_until: datetime | None = None


class NotificationUpdate(StrictModel):
    read: bool | None = None
    dismissed: bool | None = None
