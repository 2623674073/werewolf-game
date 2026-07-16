from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ReviewStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class DossierPlayer(BaseModel):
    name: str
    character: str
    role: str
    is_alive: bool


class DossierEvent(BaseModel):
    seq: int = Field(gt=0)
    phase: str
    type: str
    visibility: str
    recipients: list[str] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)


class GameDossier(BaseModel):
    game_id: str
    winner: str
    total_rounds: int = Field(ge=0)
    players: list[DossierPlayer]
    events: list[DossierEvent]


class TurningPoint(BaseModel):
    title: str = Field(min_length=1, max_length=80)
    analysis: str = Field(min_length=1, max_length=500)
    event_seqs: list[int] = Field(min_length=1)


class PlayerReview(BaseModel):
    player: str
    character: str
    role: str
    score: float = Field(ge=0, le=10)
    role_completion: str = Field(min_length=1, max_length=300)
    highlights: list[str] = Field(default_factory=list, max_length=4)
    mistakes: list[str] = Field(default_factory=list, max_length=4)
    evidence_event_seqs: list[int] = Field(min_length=1)

    @field_validator("score")
    @classmethod
    def round_score(cls, value: float) -> float:
        return round(value, 1)


class GameReviewResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=80)
    overview: str = Field(min_length=1, max_length=1200)
    turning_points: list[TurningPoint] = Field(min_length=2, max_length=5)
    winning_factors: list[str] = Field(min_length=1, max_length=5)
    player_reviews: list[PlayerReview] = Field(min_length=1)
    mvp: str
    closing_comment: str = Field(min_length=1, max_length=600)


@dataclass(slots=True)
class GameReview:
    game_id: str
    status: ReviewStatus = ReviewStatus.PENDING
    result: GameReviewResult | None = None
    error_code: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
