from __future__ import annotations

import asyncio
import random
from pathlib import Path

import pytest

from werewolf_game.application.engine import GameEngine
from werewolf_game.application.events import EventBroker, EventCoordinator
from werewolf_game.application.service import GameService
from werewolf_game.domain.models import GameEvent, GameStatus, Phase, Visibility
from werewolf_game.infrastructure.database import Database
from werewolf_game.infrastructure.demo import DemoAgentRuntime
from werewolf_game.infrastructure.repository import SqliteGameRepository


async def test_four_games_and_twenty_sse_observers_finish_consistently(
    tmp_path: Path,
) -> None:
    database = Database(f"sqlite+aiosqlite:///{(tmp_path / 'soak.db').as_posix()}")
    await database.create_schema()
    repository = SqliteGameRepository(database.session_factory)
    broker = EventBroker(queue_size=500, max_subscribers=25)
    events = EventCoordinator(repository, broker)
    runtime = DemoAgentRuntime(chunk_delay=0)
    seed = 0

    def engine() -> GameEngine:
        nonlocal seed
        seed += 1
        return GameEngine(
            runtime,
            repository,
            events,
            rng=random.Random(seed),
            discussion_rounds=1,
        )

    service = GameService(
        repository,
        engine,
        max_concurrent_games=4,
        events=events,
    )
    games = [await service.create_game(6) for _ in range(4)]
    streams = [
        broker.subscribe(game.id, include_private=observer == 0)
        for game in games
        for observer in range(5)
    ]

    async def consume(stream) -> list[GameEvent]:
        return [event async for event in stream if isinstance(event, GameEvent)]

    viewers = [asyncio.create_task(consume(stream)) for stream in streams]
    for game in games:
        await service.start_game(game.id)
    observed = await asyncio.wait_for(asyncio.gather(*viewers), timeout=20)

    for index, game in enumerate(games):
        saved = await repository.get_game(game.id)
        assert saved is not None
        assert saved.status in {GameStatus.COMPLETED, GameStatus.DRAW}
        for timeline in observed[index * 5 : index * 5 + 5]:
            seqs = [event.seq for event in timeline]
            assert seqs == sorted(set(seqs))
            assert timeline[-1].type == "game_finished"
    assert broker.subscriber_count == 0
    await service.shutdown()
    await database.dispose()


async def test_slow_subscriber_is_disconnected_when_bounded_queue_overflows() -> None:
    broker = EventBroker(queue_size=1, max_subscribers=1)
    stream = broker.subscribe("slow", include_private=False)
    first = GameEvent(
        "slow",
        1,
        "day_started",
        Phase.DAY,
        Visibility.PUBLIC,
        (),
        {"round": 1},
    )
    second = GameEvent(
        "slow",
        2,
        "game_finished",
        Phase.FINISHED,
        Visibility.PUBLIC,
        (),
        {"winner": "villagers"},
    )
    await broker.publish(first)
    await broker.publish(second)
    with pytest.raises(StopAsyncIteration):
        await anext(stream)
    assert broker.subscriber_count == 0
