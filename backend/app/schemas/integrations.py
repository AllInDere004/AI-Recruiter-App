from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NotificationPreferenceUpdate(StrictModel):
    categories: dict[Literal["application", "interview", "deadline", "follow_up", "account"], bool]
    email_enabled: bool = False
    timezone: str = Field(min_length=1, max_length=100)
    quiet_hours: dict[str, str] = Field(default_factory=dict)
    expected_version: int | None = Field(default=None, gt=0)


class OAuthCallback(StrictModel):
    state: str = Field(min_length=32, max_length=500)
    code: str = Field(min_length=1, max_length=4000)


class GmailSendApproval(StrictModel):
    generation_version_id: int = Field(gt=0)
    recipient: EmailStr
    subject: str = Field(min_length=1, max_length=500)
    body: str = Field(min_length=1, max_length=100_000)
    confirm_review: Literal[True]
    idempotency_key: str = Field(min_length=16, max_length=100)
