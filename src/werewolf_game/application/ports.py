from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from pydantic import BaseModel

from werewolf_game.domain.models import GameEvent, GameState


class AgentRuntime(Protocol):
    async def setup(self, game: GameState, prompts: dict[str, str]) -> None: ...

    async def discuss(
        self,
        game_id: str,
        players: Sequence[str],
        announcement: str,
        rounds: int,
    ) -> list[dict[str, str]]: ...

    async def decide(
        self,
        game_id: str,
        player: str,
        prompt: str,
        schema: type[BaseModel],
    ) -> BaseModel | None: ...

    async def close(self, game_id: str) -> None: ...


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
