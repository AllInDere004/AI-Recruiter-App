from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


InterviewType = Literal["technical", "hr", "behavioral", "project"]
Difficulty = Literal["beginner", "intermediate", "advanced"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class InterviewStart(StrictModel):
    resume_version_id: int = Field(gt=0)
    job_id: int | None = Field(default=None, gt=0)
    interview_type: InterviewType
    difficulty: Difficulty
    question_count: int = Field(default=5, ge=1, le=20)
    time_limit_minutes: int | None = Field(default=None, ge=5, le=180)


class InterviewStateUpdate(StrictModel):
    expected_version: int = Field(gt=0)
    action: Literal["pause", "resume"]


class AnswerSubmit(StrictModel):
    answer: str = Field(min_length=1, max_length=20_000)

    @field_validator("answer")
    @classmethod
    def meaningful_answer(cls, value: str):
        value = value.strip()
        if not value:
            raise ValueError("Answer cannot be blank.")
        return value


class GeneratedQuestion(StrictModel):
    question: str = Field(min_length=10, max_length=1000)
    question_type: InterviewType
    competency: str = Field(min_length=2, max_length=200)
    rubric: dict[str, str] = Field(min_length=2, max_length=8)


class GeneratedQuestionSet(StrictModel):
    questions: list[GeneratedQuestion] = Field(min_length=1, max_length=20)


class CategoryScore(StrictModel):
    category: str = Field(min_length=2, max_length=100)
    score: int = Field(ge=0, le=100)
    rationale: str = Field(min_length=1, max_length=1000)


class QuestionFeedback(StrictModel):
    question_id: int = Field(gt=0)
    categories: list[CategoryScore] = Field(min_length=3, max_length=8)
    evidence_quotes: list[str] = Field(default_factory=list, max_length=8)
    strengths: list[str] = Field(default_factory=list, max_length=8)
    improvements: list[str] = Field(default_factory=list, max_length=8)
    sample_improved_answer: str = Field(min_length=1, max_length=10_000)


class SessionFeedback(StrictModel):
    feedback: list[QuestionFeedback] = Field(min_length=1, max_length=20)
