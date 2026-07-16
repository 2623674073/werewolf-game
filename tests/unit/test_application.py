from __future__ import annotations

import asyncio
import random
from collections.abc import AsyncIterator, Sequence
from typing import Any

import pytest
from pydantic import BaseModel

from werewolf_game.application.engine import GameEngine
from werewolf_game.application.errors import CapacityError, ConflictError, NotFoundError
from werewolf_game.application.events import EventBroker, EventCoordinator
from werewolf_game.application.ports import DiscussionActivity
from werewolf_game.application.service import GameService
from werewolf_game.domain.models import GameEvent, GameState, GameStatus, Visibility
from werewolf_game.domain.reviews import GameReview


class MemoryRepository:
    def __init__(self) -> None:
        self.games: dict[str, GameState] = {}
        self.events: dict[str, list[GameEvent]] = {}

    async def create_game(self, game: GameState) -> GameState:
        self.games[game.id] = game
        return game

    async def get_game(self, game_id: str) -> GameState | None:
        return self.games.get(game_id)

    async def list_games(self, offset: int, limit: int) -> list[GameState]:
        return list(self.games.values())[offset : offset + limit]

    async def delete_game(self, game_id: str) -> bool:
        if self.games.pop(game_id, None) is None:
            return False
        self.events.pop(game_id, None)
        return True

    async def save_game(self, game: GameState) -> None:
        self.games[game.id] = game

    async def append_event(self, event: GameEvent) -> GameEvent:
        events = self.events.setdefault(event.game_id, [])
        stored = GameEvent(
            game_id=event.game_id,
            seq=len(events) + 1,
            type=event.type,
            phase=event.phase,
            visibility=event.visibility,
            recipients=event.recipients,
            payload=event.payload,
            created_at=event.created_at,
        )
        events.append(stored)
        return stored

    async def list_events(
        self, game_id: str, after_seq: int, include_private: bool
    ) -> list[GameEvent]:
        return [
            event
            for event in self.events.get(game_id, [])
            if event.seq > after_seq
            and (include_private or event.visibility is Visibility.PUBLIC)
        ]

    async def mark_running_interrupted(self) -> int:
        return 0

    async def get_review(self, game_id: str) -> GameReview | None:
        return None

    async def ping(self) -> bool:
        return True


class FakeRuntime:
    def __init__(self) -> None:
        self.closed: list[str] = []

    async def setup(self, game: GameState, prompts: dict[str, str]) -> None:
        assert set(prompts) == {player.name for player in game.players}

    async def discuss(
        self, game_id: str, players: Sequence[str], announcement: str, rounds: int
    ) -> AsyncIterator[DiscussionActivity]:
        for name in players:
            yield DiscussionActivity("turn_started", name, 1)
            yield DiscussionActivity("speech", name, 1, f"{name}发言")

    async def decide(
        self, game_id: str, player: str, prompt: str, schema: type[BaseModel]
    ) -> BaseModel | None:
        fields = schema.model_fields
        if "vote" in fields:
            target = next(
                name
                for name in _literal_values(fields["vote"].annotation)
                if name != player
            )
            return schema(vote=target, reason="测试", suspicion_level=5)
        if "target" in fields and "kill_strategy" in fields:
            return schema(
                target=_literal_values(fields["target"].annotation)[0],
                kill_strategy="测试",
            )
        if "check_reason" in fields:
            return schema(
                target=_literal_values(fields["target"].annotation)[0],
                check_reason="测试",
                priority_level=5,
            )
        if "shoot" in fields:
            return schema(shoot=False)
        if "action" in fields:
            return schema(action="不行动")
        return None

    async def close(self, game_id: str) -> None:
        self.closed.append(game_id)


def _literal_values(annotation: Any) -> tuple[str, ...]:
    return tuple(annotation.__args__)


async def _next(stream: AsyncIterator[GameEvent]) -> GameEvent:
    return await anext(stream)


async def test_event_broker_filters_private_events_for_public_view() -> None:
    repository = MemoryRepository()
    broker = EventBroker(queue_size=4)
    coordinator = EventCoordinator(repository, broker)
    game = GameState(id="game-1", player_count=6)

    public_stream = broker.subscribe("game-1", include_private=False)
    god_stream = broker.subscribe("game-1", include_private=True)
    public_task = asyncio.create_task(_next(public_stream))
    god_task = asyncio.create_task(_next(god_stream))
    await asyncio.sleep(0)

    await coordinator.emit(
        game, "identity", {"role": "狼人"}, visibility=Visibility.PRIVATE
    )
    private = await asyncio.wait_for(god_task, 0.2)
    assert private.type == "identity"
    assert not public_task.done()

    await coordinator.emit(game, "day_started", {}, visibility=Visibility.PUBLIC)
    public = await asyncio.wait_for(public_task, 0.2)
    assert public.type == "day_started"
    await public_stream.aclose()
    await god_stream.aclose()


async def test_engine_runs_offline_game_and_closes_runtime() -> None:
    repository = MemoryRepository()
    runtime = FakeRuntime()
    events = EventCoordinator(repository, EventBroker())
    state = GameState(id="game-2", player_count=6)
    await repository.create_game(state)
    engine = GameEngine(
        runtime,
        repository,
        events,
        rng=random.Random(2),
        max_rounds=2,
    )

    await engine.run(state)

    assert state.status in {GameStatus.COMPLETED, GameStatus.DRAW}
    assert state.finished_at is not None
    assert runtime.closed == ["game-2"]
    assert repository.events["game-2"][-1].type == "game_finished"
    event_types = {event.type for event in repository.events["game-2"]}
    assert {
        "werewolf_vote",
        "witch_action",
        "day_vote",
        "speaker_turn_started",
        "roles_revealed",
    } <= event_types
    assert all(player.persona_tags for player in state.players)


async def test_engine_persists_public_speech_without_moderation() -> None:
    repository = MemoryRepository()
    events = EventCoordinator(repository, EventBroker())
    state = GameState(id="unmoderated", player_count=6)
    await repository.create_game(state)

    await GameEngine(
        FakeRuntime(),
        repository,
        events,
        rng=random.Random(2),
        max_rounds=1,
    ).run(state)

    public_speeches = [
        event
        for event in repository.events[state.id]
        if event.type == "speech" and event.visibility is Visibility.PUBLIC
    ]
    assert public_speeches
    assert {str(event.payload["content"]).split("发言")[0] for event in public_speeches}
    assert not [
        event
        for event in repository.events[state.id]
        if event.type == "speech_moderated"
    ]


async def test_service_rejects_duplicate_start_and_can_cancel() -> None:
    repository = MemoryRepository()
    broker = EventBroker()
    events = EventCoordinator(repository, broker)
    started = asyncio.Event()
    release = asyncio.Event()

    class BlockingEngine:
        async def run(self, game: GameState) -> None:
            game.status = GameStatus.RUNNING
            started.set()
            await release.wait()

    service = GameService(
        repository,
        lambda: BlockingEngine(),
        max_concurrent_games=1,
        events=events,
    )
    game = await service.create_game(6)
    await service.start_game(game.id)
    await started.wait()

    try:
        await service.start_game(game.id)
    except Exception as exc:
        assert getattr(exc, "code", None) == "game_already_started"
    else:
        raise AssertionError("duplicate start must fail")

    await service.cancel_game(game.id)
    assert game.status is GameStatus.CANCELLED
    assert repository.events[game.id][-1].type == "game_cancelled"


async def test_service_enforces_capacity_and_shutdown_marks_interrupted() -> None:
    repository = MemoryRepository()
    blocker = asyncio.Event()

    class BlockingEngine:
        async def run(self, game: GameState) -> None:
            await blocker.wait()

    service = GameService(repository, lambda: BlockingEngine(), max_concurrent_games=1)
    first = await service.create_game(6)
    second = await service.create_game(6)
    await service.start_game(first.id)
    with pytest.raises(CapacityError):
        await service.start_game(second.id)
    with pytest.raises(NotFoundError):
        await service.require_game("missing")

    await service.shutdown()
    assert first.status is GameStatus.INTERRUPTED


@pytest.mark.parametrize(
    "status",
    [
        GameStatus.COMPLETED,
        GameStatus.DRAW,
        GameStatus.CANCELLED,
        GameStatus.INTERRUPTED,
        GameStatus.FAILED,
    ],
)
async def test_service_deletes_terminal_games(status: GameStatus) -> None:
    repository = MemoryRepository()
    game = GameState(id=status.value, player_count=6, status=status)
    await repository.create_game(game)
    service = GameService(repository, lambda: FakeRuntime(), max_concurrent_games=1)

    await service.delete_game(game.id)

    assert await repository.get_game(game.id) is None


@pytest.mark.parametrize("status", [GameStatus.CREATED, GameStatus.RUNNING])
async def test_service_rejects_deleting_non_terminal_games(status: GameStatus) -> None:
    repository = MemoryRepository()
    game = GameState(id=status.value, player_count=6, status=status)
    await repository.create_game(game)
    service = GameService(repository, lambda: FakeRuntime(), max_concurrent_games=1)

    with pytest.raises(ConflictError, match="只有已结束") as error:
        await service.delete_game(game.id)

    assert error.value.code == "game_not_deletable"


async def test_service_shutdown_interrupts_multiple_games_and_emits_events() -> None:
    repository = MemoryRepository()
    events = EventCoordinator(repository, EventBroker())
    blocker = asyncio.Event()

    class BlockingEngine:
        async def run(self, game: GameState) -> None:
            await blocker.wait()

    service = GameService(
        repository,
        lambda: BlockingEngine(),
        max_concurrent_games=2,
        events=events,
    )
    games = [await service.create_game(6) for _ in range(2)]
    for game in games:
        await service.start_game(game.id)

    await service.shutdown()

    assert all(game.status is GameStatus.INTERRUPTED for game in games)
    assert all(
        repository.events[game.id][-1].type == "game_interrupted" for game in games
    )


async def test_engine_marks_fatal_runtime_failure_without_leaking_exception() -> None:
    repository = MemoryRepository()
    runtime = FakeRuntime()

    async def fail_setup(game: GameState, prompts: dict[str, str]) -> None:
        raise RuntimeError("provider secret detail")

    runtime.setup = fail_setup  # type: ignore[method-assign]
    events = EventCoordinator(repository, EventBroker())
    state = GameState(id="failed", player_count=6)
    await repository.create_game(state)

    await GameEngine(runtime, repository, events).run(state)

    assert state.status is GameStatus.FAILED
    assert state.error_code == "game_execution_failed"
    assert repository.events["failed"][-1].payload == {
        "error_code": "game_execution_failed"
    }
