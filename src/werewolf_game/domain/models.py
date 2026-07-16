from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class GameStatus(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    DRAW = "draw"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"
    FAILED = "failed"


class Phase(StrEnum):
    SETUP = "setup"
    NIGHT = "night"
    DAY = "day"
    FINISHED = "finished"


class Visibility(StrEnum):
    PUBLIC = "public"
    PRIVATE = "private"
    INTERNAL = "internal"


@dataclass(slots=True)
class GamePlayer:
    name: str
    character: str
    role: str
    is_alive: bool = True
    has_antidote: bool | None = None
    has_poison: bool | None = None
    persona_tags: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        is_witch = self.role == "女巫"
        if self.has_antidote is None:
            self.has_antidote = is_witch
        if self.has_poison is None:
            self.has_poison = is_witch

    def eliminate(self) -> None:
        self.is_alive = False


@dataclass(slots=True)
class GameState:
    id: str
    player_count: int
    status: GameStatus = GameStatus.CREATED
    phase: Phase = Phase.SETUP
    round_number: int = 0
    players: list[GamePlayer] = field(default_factory=list)
    winner: str | None = None
    error_code: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    finished_at: datetime | None = None


@dataclass(slots=True, frozen=True)
class GameEvent:
    game_id: str
    seq: int
    type: str
    phase: Phase
    visibility: Visibility
    recipients: tuple[str, ...]
    payload: dict[str, Any]
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
