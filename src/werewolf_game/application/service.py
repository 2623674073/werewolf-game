from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol
from uuid import uuid4

from werewolf_game.application.errors import CapacityError, ConflictError, NotFoundError
from werewolf_game.application.events import EventCoordinator
from werewolf_game.application.ports import GameRepository
from werewolf_game.domain.models import GameState, GameStatus, Phase
from werewolf_game.domain.rules import validate_player_count

logger = logging.getLogger(__name__)


class RunnableEngine(Protocol):
    async def run(self, game: GameState) -> None: ...


class GameService:
    def __init__(
        self,
        repository: GameRepository,
        engine_factory: Callable[[], RunnableEngine],
        *,
        max_concurrent_games: int,
        events: EventCoordinator | None = None,
    ) -> None:
        self.repository = repository
        self.engine_factory = engine_factory
        self.max_concurrent_games = max_concurrent_games
        self.events = events
        self._tasks: dict[str, asyncio.Task[None]] = {}

    async def create_game(self, player_count: int) -> GameState:
        validate_player_count(player_count)
        return await self.repository.create_game(
            GameState(id=str(uuid4()), player_count=player_count)
        )

    async def start_game(self, game_id: str) -> GameState:
        game = await self.require_game(game_id)
        if game.status is not GameStatus.CREATED or game_id in self._tasks:
            raise ConflictError("game_already_started", "游戏已经启动或已结束")
        if len(self._tasks) >= self.max_concurrent_games:
            raise CapacityError("game_capacity_reached", "并发游戏数已达到上限")
        game.status = GameStatus.RUNNING
        game.started_at = datetime.now(UTC)
        await self.repository.save_game(game)
        task = asyncio.create_task(self._execute(game), name=f"game:{game.id}")
        self._tasks[game.id] = task
        return game

    async def _execute(self, game: GameState) -> None:
        try:
            await self.engine_factory().run(game)
        finally:
            self._tasks.pop(game.id, None)

    async def cancel_game(self, game_id: str) -> GameState:
        game = await self.require_game(game_id)
        task = self._tasks.get(game_id)
        if task is None or task.done():
            raise ConflictError("game_not_running", "游戏当前未运行")
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        game.status = GameStatus.CANCELLED
        game.phase = Phase.FINISHED
        game.finished_at = datetime.now(UTC)
        await self.repository.save_game(game)
        if self.events is not None:
            await self.events.emit(game, "game_cancelled", {})
            await self.events.broker.close_game(game.id)
        return game

    async def require_game(self, game_id: str) -> GameState:
        game = await self.repository.get_game(game_id)
        if game is None:
            raise NotFoundError("game_not_found", "游戏不存在")
        return game

    async def shutdown(self) -> None:
        running = list(self._tasks.items())
        games = await asyncio.gather(
            *(self.repository.get_game(game_id) for game_id, _ in running),
            return_exceptions=True,
        )
        for _, task in running:
            task.cancel()
        await asyncio.gather(
            *(task for _, task in running),
            return_exceptions=True,
        )
        for (game_id, _), game_or_error in zip(running, games, strict=True):
            if isinstance(game_or_error, BaseException):
                logger.error(
                    "failed to load running game during shutdown",
                    extra={"game_id": game_id},
                )
                continue
            game = game_or_error
            if game is None or game.status is not GameStatus.RUNNING:
                continue
            try:
                game.status = GameStatus.INTERRUPTED
                game.phase = Phase.FINISHED
                game.finished_at = datetime.now(UTC)
                await self.repository.save_game(game)
                if self.events is not None:
                    await self.events.emit(
                        game,
                        "game_interrupted",
                        {"error_code": "service_shutdown"},
                    )
                    await self.events.broker.close_game(game.id)
            except Exception:
                logger.exception(
                    "failed to persist interrupted game during shutdown",
                    extra={"game_id": game_id},
                )
