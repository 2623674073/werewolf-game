from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator, Sequence
from typing import Any

from werewolf_game.application.ports import GameRepository
from werewolf_game.domain.models import GameEvent, GameState, Visibility

logger = logging.getLogger(__name__)


class EventBroker:
    def __init__(self, queue_size: int = 100) -> None:
        self._queue_size = queue_size
        self._subscribers: dict[
            str, list[tuple[bool, asyncio.Queue[GameEvent | None]]]
        ] = {}

    async def publish(self, event: GameEvent) -> None:
        subscribers = list(self._subscribers.get(event.game_id, []))
        for include_private, queue in subscribers:
            if not include_private and event.visibility is not Visibility.PUBLIC:
                continue
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                self._remove(event.game_id, queue)
                while not queue.empty():
                    queue.get_nowait()
                queue.put_nowait(None)

    async def close_game(self, game_id: str) -> None:
        for _, queue in self._subscribers.pop(game_id, []):
            if queue.full():
                queue.get_nowait()
            queue.put_nowait(None)

    async def subscribe(
        self, game_id: str, *, include_private: bool
    ) -> AsyncGenerator[GameEvent, None]:
        queue: asyncio.Queue[GameEvent | None] = asyncio.Queue(self._queue_size)
        item = (include_private, queue)
        self._subscribers.setdefault(game_id, []).append(item)
        try:
            while True:
                event = await queue.get()
                if event is None:
                    return
                yield event
        finally:
            self._remove(game_id, queue)

    def _remove(self, game_id: str, queue: asyncio.Queue[GameEvent | None]) -> None:
        current = self._subscribers.get(game_id, [])
        self._subscribers[game_id] = [item for item in current if item[1] is not queue]
        if not self._subscribers[game_id]:
            self._subscribers.pop(game_id, None)


class EventCoordinator:
    def __init__(self, repository: GameRepository, broker: EventBroker) -> None:
        self.repository = repository
        self.broker = broker

    async def emit(
        self,
        game: GameState,
        event_type: str,
        payload: dict[str, Any],
        *,
        visibility: Visibility = Visibility.PUBLIC,
        recipients: Sequence[str] = (),
    ) -> GameEvent:
        stored = await self.repository.append_event(
            GameEvent(
                game_id=game.id,
                seq=0,
                type=event_type,
                phase=game.phase,
                visibility=visibility,
                recipients=tuple(recipients),
                payload=payload,
            )
        )
        await self.broker.publish(stored)
        logger.info(
            "game event persisted",
            extra={
                "game_id": game.id,
                "phase": game.phase.value,
                "event_type": event_type,
            },
        )
        return stored
