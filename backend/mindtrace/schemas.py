from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from mindtrace.config import get_settings
from mindtrace.modes import Mode


class AnalyzeRequest(BaseModel):
    problem: str = Field(description="The problem statement.")
    reasoning: str = Field(description="The person's reasoning or answer.")
    mode: Mode = "education"

    @field_validator("problem", "reasoning")
    @classmethod
    def _not_blank_and_bounded(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be empty")
        limit = get_settings().max_input_chars
        if len(value) > limit:
            raise ValueError(f"must be at most {limit} characters")
        return value


class Section(BaseModel):
    key: str
    title: str
    content: str | list[str]


class BlockInfo(BaseModel):
    reason: str
    message: str


class Meta(BaseModel):
    model: str
    latency_ms: int
    judge_called: bool
    missing_fields: list[str] = Field(default_factory=list)


class AnalyzeResponse(BaseModel):
    mode: Mode
    status: Literal["ok", "blocked"]
    mistake_type: str | None = None
    reasoning_pattern: str | None = None
    confidence: str | None = None
    agreement: str | None = None
    explanation: str | None = None
    # Every field the mode produced, in display order (summary fields excluded).
    sections: list[Section] = Field(default_factory=list)
    # Present only when status == "blocked". A blocked response never carries model text.
    block: BlockInfo | None = None
    meta: Meta


class ModeInfo(BaseModel):
    key: Mode
    label: str
    fields: list[str]
