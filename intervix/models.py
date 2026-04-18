from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class InterviXModel(BaseModel):
    model_config = ConfigDict(use_enum_values=True)


class ProviderChoice(str, Enum):
    auto = "auto"
    gemini = "gemini"
    ollama = "ollama"


class Difficulty(str, Enum):
    beginner = "beginner"
    mid = "mid"
    senior = "senior"


class InterviewType(str, Enum):
    technical = "technical"
    hr = "hr"
    behavioral = "behavioral"
    system_design = "system_design"
    mixed = "mixed"


class CompanyStyle(str, Enum):
    neutral = "neutral"
    google = "google"
    startup = "startup"
    faang = "faang"


class SessionStatus(str, Enum):
    starting = "starting"
    awaiting_answer = "awaiting_answer"
    evaluating = "evaluating"
    completed = "completed"
    interrupted = "interrupted"
    error = "error"


class ModelReply(InterviXModel):
    provider: str
    model_name: str
    text: str
    notice: str | None = None


class ScoreCard(InterviXModel):
    clarity: int = Field(default=6, ge=1, le=10)
    relevance: int = Field(default=6, ge=1, le=10)
    technical_depth: int = Field(default=6, ge=1, le=10)
    confidence: int = Field(default=6, ge=1, le=10)

    @property
    def average(self) -> float:
        return round(
            (self.clarity + self.relevance + self.technical_depth + self.confidence) / 4,
            2,
        )


class FeedbackPayload(InterviXModel):
    strengths: list[str] = Field(default_factory=list)
    weak_areas: list[str] = Field(default_factory=list)
    coaching: list[str] = Field(default_factory=list)
    ideal_answer: str = "Show a clearer structure, stronger evidence, and sharper trade-offs."
    recommendation: str = "Keep answers specific and measurable."
    star_tip: str | None = None
    scores: ScoreCard = Field(default_factory=ScoreCard)
    weak_answer: bool = False
    follow_up_reason: str | None = None
    summary_blurb: str | None = None

    @field_validator("strengths", "weak_areas", "coaching", mode="before")
    @classmethod
    def _coerce_list(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return []


class SessionSummary(InterviXModel):
    final_score: int = Field(default=60, ge=0, le=100)
    strengths: list[str] = Field(default_factory=list)
    weak_areas: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    top_improvements: list[str] = Field(default_factory=list)
    readiness: str = "Keep practicing."
    closing_message: str = "You completed the session. Review the notes and try again with a harder setup."

    @field_validator("strengths", "weak_areas", "recommendations", "top_improvements", mode="before")
    @classmethod
    def _coerce_summary_lists(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return []


class SessionConfig(InterviXModel):
    role: str = Field(min_length=2, max_length=60)
    provider: ProviderChoice = ProviderChoice.auto
    question_count: int = Field(default=4, ge=2, le=8)
    difficulty: Difficulty = Difficulty.mid
    interview_type: InterviewType = InterviewType.mixed
    company_style: CompanyStyle = CompanyStyle.neutral
    language: str = Field(default="English", min_length=2, max_length=24)

    @field_validator("role")
    @classmethod
    def _normalize_role(cls, value: str) -> str:
        cleaned = " ".join((value or "").split()).strip()
        if not cleaned:
            raise ValueError("Role is required.")
        return cleaned[:60]

    @field_validator("language")
    @classmethod
    def _normalize_language(cls, value: str) -> str:
        cleaned = " ".join((value or "English").split()).strip()
        return cleaned or "English"


class TurnRecord(InterviXModel):
    turn_index: int
    focus_label: str
    question: str
    answer: str
    feedback: FeedbackPayload
    provider: str
    model: str
    created_at: str


class SessionSnapshot(InterviXModel):
    session_id: str
    correlation_id: str
    config: SessionConfig
    progress_labels: list[str] = Field(default_factory=list)
    estimated_minutes: int = 12
    active_provider: str = ""
    active_model: str = ""
    status: SessionStatus = SessionStatus.starting
    current_question_index: int = 0
    current_question: str | None = None
    waiting_for_answer: bool = False
    turns: list[TurnRecord] = Field(default_factory=list)
    summary: SessionSummary | None = None
    created_at: str
    updated_at: str


class SessionHistoryItem(InterviXModel):
    session_id: str
    role: str
    difficulty: str
    interview_type: str
    company_style: str
    question_count: int
    active_provider: str
    final_score: int | None = None
    status: str
    created_at: str
    updated_at: str
