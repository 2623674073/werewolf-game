from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class ModerationStatus(StrEnum):
    ALLOWED = "allowed"
    BLOCKED = "blocked"
    UNAVAILABLE = "unavailable"


class ModerationCategory(StrEnum):
    HARASSMENT = "harassment"
    HATE = "hate"
    SEXUAL = "sexual"
    SELF_HARM = "self_harm"
    PERSONAL_DATA = "personal_data"
    PROMPT_INJECTION = "prompt_injection"
    OTHER = "other"


class ModerationDecision(BaseModel):
    status: ModerationStatus
    categories: list[ModerationCategory] = Field(default_factory=list)
    reason: str = Field(default="", max_length=200)
