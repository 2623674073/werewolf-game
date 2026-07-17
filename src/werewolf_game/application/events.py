from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from werewolf_game.application.ports import GameRepository
from werewolf_game.domain.models import GameEvent, GameState, Phase, Visibility

logger = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class TransientGameEvent:
    game_id: str
    type: str
    phase: Phase
    visibility: Visibility
    recipients: tuple[str, ...]
    payload: dict[str, Any]
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


StreamEvent = GameEvent | TransientGameEvent


class EventSubscription(AsyncIterator[StreamEvent]):
    def __init__(
        self,
        broker: EventBroker,
        game_id: str,
        queue: asyncio.Queue[StreamEvent | None],
    ) -> None:
        self._broker = broker
        self._game_id = game_id
        self._queue = queue
        self._closed = False

    def __aiter__(self) -> EventSubscription:
        return self

    async def __anext__(self) -> StreamEvent:
        if self._closed:
            raise StopAsyncIteration
        event = await self._queue.get()
        if event is None:
            await self.aclose()
            raise StopAsyncIteration
        return event

    async def aclose(self) -> None:
        if not self._closed:
            self._closed = True
            self._broker._remove(self._game_id, self._queue)


class EventBroker:
    def __init__(self, queue_size: int = 100, max_subscribers: int = 100) -> None:
        self._queue_size = queue_size
        self._max_subscribers = max_subscribers
        self._subscribers: dict[
            str, list[tuple[bool, asyncio.Queue[StreamEvent | None]]]
        ] = {}

    async def publish(self, event: StreamEvent) -> None:
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

    def subscribe(self, game_id: str, *, include_private: bool) -> EventSubscription:
        if self.subscriber_count >= self._max_subscribers:
            raise SubscriptionCapacityError
        queue: asyncio.Queue[StreamEvent | None] = asyncio.Queue(self._queue_size)
        item = (include_private, queue)
        self._subscribers.setdefault(game_id, []).append(item)
        return EventSubscription(self, game_id, queue)

    @property
    def subscriber_count(self) -> int:
        return sum(len(items) for items in self._subscribers.values())

    def _remove(self, game_id: str, queue: asyncio.Queue[StreamEvent | None]) -> None:
        current = self._subscribers.get(game_id, [])
        self._subscribers[game_id] = [item for item in current if item[1] is not queue]
        if not self._subscribers[game_id]:
            self._subscribers.pop(game_id, None)


class SubscriptionCapacityError(RuntimeError):
    pass


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

    async def emit_transient(
        self,
        game: GameState,
        event_type: str,
        payload: dict[str, Any],
        *,
        visibility: Visibility = Visibility.PUBLIC,
        recipients: Sequence[str] = (),
    ) -> TransientGameEvent:
        event = TransientGameEvent(
            game_id=game.id,
            type=event_type,
            phase=game.phase,
            visibility=visibility,
            recipients=tuple(recipients),
            payload=payload,
        )
        await self.broker.publish(event)
        return event
