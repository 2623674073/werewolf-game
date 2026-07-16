from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from werewolf_game.application.errors import ConflictError, NotFoundError
from werewolf_game.application.ports import GameHistorian, GameRepository
from werewolf_game.domain.models import GameState, GameStatus
from werewolf_game.domain.reviews import (
    DossierEvent,
    DossierPlayer,
    GameDossier,
    GameReview,
    ReviewStatus,
)

logger = logging.getLogger(__name__)


class GameReviewService:
    def __init__(
        self,
        repository: GameRepository,
        historian: GameHistorian,
        *,
        max_concurrent_reviews: int = 1,
    ) -> None:
        self.repository = repository
        self.historian = historian
        self._semaphore = asyncio.Semaphore(max_concurrent_reviews)
        self._tasks: dict[str, asyncio.Task[None]] = {}

    async def request_review(self, game_id: str) -> GameReview:
        game = await self._require_reviewable_game(game_id)
        current = await self.repository.get_review(game_id)
        if current is not None:
            if current.status is ReviewStatus.COMPLETED:
                return current
            if current.status is ReviewStatus.PENDING:
                raise ConflictError("review_in_progress", "史官正在撰写本局复盘")
            current.status = ReviewStatus.PENDING
            current.result = None
            current.error_code = None
            current.created_at = datetime.now(UTC)
            current.completed_at = None
            await self.repository.save_review(current)
            review = current
        else:
            review = await self.repository.create_review(GameReview(game_id=game.id))
        self._tasks[game_id] = asyncio.create_task(
            self._execute(game, review),
            name=f"review:{game_id}",
        )
        return review

    async def get_review(self, game_id: str) -> GameReview:
        if await self.repository.get_game(game_id) is None:
            raise NotFoundError("game_not_found", "游戏不存在")
        review = await self.repository.get_review(game_id)
        if review is None:
            raise NotFoundError("game_review_not_found", "尚未生成本局复盘")
        return review

    async def _require_reviewable_game(self, game_id: str) -> GameState:
        game = await self.repository.get_game(game_id)
        if game is None:
            raise NotFoundError("game_not_found", "游戏不存在")
        if game.status not in {GameStatus.COMPLETED, GameStatus.DRAW}:
            raise ConflictError(
                "game_not_reviewable",
                "只有正常完成或平局的对局可以生成复盘",
            )
        return game

    async def _execute(self, game: GameState, review: GameReview) -> None:
        try:
            async with self._semaphore:
                events = await self.repository.list_events(game.id, 0, True)
                dossier = GameDossier(
                    game_id=game.id,
                    winner=game.winner or "draw",
                    total_rounds=game.round_number,
                    players=[
                        DossierPlayer(
                            name=player.name,
                            character=player.character,
                            role=player.role,
                            is_alive=player.is_alive,
                        )
                        for player in game.players
                    ],
                    events=[
                        DossierEvent(
                            seq=event.seq,
                            phase=event.phase.value,
                            type=event.type,
                            visibility=event.visibility.value,
                            recipients=list(event.recipients),
                            payload=event.payload,
                        )
                        for event in events
                    ],
                )
                review.result = await self.historian.generate_review(dossier)
                review.status = ReviewStatus.COMPLETED
                review.error_code = None
        except asyncio.CancelledError:
            review.status = ReviewStatus.FAILED
            review.error_code = "service_shutdown"
            raise
        except Exception:
            review.status = ReviewStatus.FAILED
            review.error_code = "review_generation_failed"
            logger.exception(
                "game review generation failed",
                extra={"game_id": game.id},
            )
        finally:
            review.completed_at = datetime.now(UTC)
            await asyncio.shield(self.repository.save_review(review))
            self._tasks.pop(game.id, None)

    async def shutdown(self) -> None:
        tasks = list(self._tasks.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
