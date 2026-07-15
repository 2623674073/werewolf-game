from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

from pydantic import BaseModel

from werewolf_game.application.moderation import ModerationDecision
from werewolf_game.domain.models import GameEvent, GameState


@dataclass(slots=True, frozen=True)
class DiscussionActivity:
    kind: Literal["turn_started", "speech"]
    player: str
    discussion_round: int
    content: str | None = None


class AgentRuntime(Protocol):
    async def setup(self, game: GameState, prompts: dict[str, str]) -> None: ...

    def discuss(
        self,
        game_id: str,
        players: Sequence[str],
        announcement: str,
        rounds: int,
    ) -> AsyncIterator[DiscussionActivity]: ...

    async def decide(
        self,
        game_id: str,
        player: str,
        prompt: str,
        schema: type[BaseModel],
    ) -> BaseModel | None: ...

    async def close(self, game_id: str) -> None: ...


class SpeechModerator(Protocol):
    async def review_speech(
        self,
        *,
        player: str,
        phase: str,
        round_number: int,
        content: str,
    ) -> ModerationDecision: ...


class GameRepository(Protocol):
    async def create_game(self, game: GameState) -> GameState: ...
    async def get_game(self, game_id: str) -> GameState | None: ...
    async def list_games(self, offset: int, limit: int) -> list[GameState]: ...
    async def save_game(self, game: GameState) -> None: ...
    async def append_event(self, event: GameEvent) -> GameEvent: ...

    async def list_events(
        self,
        game_id: str,
        after_seq: int,
        include_private: bool,
    ) -> list[GameEvent]: ...

    async def mark_running_interrupted(self) -> int: ...
    async def ping(self) -> bool: ...
