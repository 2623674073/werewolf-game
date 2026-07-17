from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient

import werewolf_game.api.app as api_app
from werewolf_game.api.app import AppComponents, build_components, create_app
from werewolf_game.application.errors import ConflictError
from werewolf_game.application.events import EventBroker, TransientGameEvent
from werewolf_game.application.locks import GameOperationLocks
from werewolf_game.application.review_service import GameReviewService
from werewolf_game.application.service import GameService
from werewolf_game.config import Settings
from werewolf_game.domain.models import (
    GameEvent,
    GamePlayer,
    GameState,
    GameStatus,
    Phase,
    Visibility,
)
from werewolf_game.domain.reviews import GameDossier, GameReview, GameReviewResult
from werewolf_game.infrastructure.database import Database
from werewolf_game.infrastructure.repository import SqliteGameRepository

TOKEN = "test-token-with-at-least-24-chars"


class InstantEngine:
    async def run(self, game: GameState) -> None:
        game.status = GameStatus.DRAW
        game.phase = Phase.FINISHED
        game.winner = "draw"


class FakeHistorian:
    last_dossier: GameDossier | None = None

    async def generate_review(self, dossier: GameDossier) -> GameReviewResult:
        type(self).last_dossier = dossier
        evidence = dossier.events[0].seq
        return GameReviewResult.model_validate(
            {
                "title": "群雄终局",
                "overview": "本局已经完成。",
                "turning_points": [
                    {
                        "title": "局势初定",
                        "analysis": "关键事件出现。",
                        "event_seqs": [evidence],
                    },
                    {
                        "title": "胜负落定",
                        "analysis": "阵营完成目标。",
                        "event_seqs": [evidence],
                    },
                ],
                "winning_factors": ["有效利用公开信息"],
                "player_reviews": [
                    {
                        "player": player.name,
                        "character": player.character,
                        "role": player.role,
                        "score": 8,
                        "role_completion": "完成本局职责。",
                        "highlights": [],
                        "mistakes": [],
                        "evidence_event_seqs": [evidence],
                    }
                    for player in dossier.players
                ],
                "mvp": dossier.players[0].name,
                "closing_comment": "此局已入史册。",
            }
        )


async def make_client(
    tmp_path: Path,
) -> tuple[AsyncClient, Database, SqliteGameRepository]:
    settings = Settings(
        llm_api_key="test-key",
        llm_model_id="deepseek-v4-flash",
        llm_base_url="http://model.example/v1",
        app_api_token=TOKEN,
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'api.db'}",
        web_dist_dir=str(tmp_path / "missing-web"),
    )
    database = Database(settings.database_url)
    await database.create_schema()
    repository = SqliteGameRepository(database.session_factory)
    broker = EventBroker()
    operation_locks = GameOperationLocks()
    service = GameService(
        repository,
        lambda: InstantEngine(),
        max_concurrent_games=2,
        operation_locks=operation_locks,
    )
    review_service = GameReviewService(
        repository,
        FakeHistorian(),
        operation_locks=operation_locks,
    )
    app = create_app(
        AppComponents(
            settings,
            database,
            repository,
            broker,
            service,
            review_service,
        )
    )
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    return client, database, repository


def auth() -> dict[str, str]:
    return {"Authorization": f"Bearer {TOKEN}"}


async def test_default_component_factory_supports_offline_demo_mode(
    tmp_path: Path,
) -> None:
    settings = Settings(
        runtime_mode="demo",
        app_api_token=TOKEN,
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'demo.db').as_posix()}",
        web_dist_dir=str(tmp_path / "missing-web"),
    )
    components = build_components(settings)
    await components.database.create_schema()
    client = AsyncClient(
        transport=ASGITransport(app=create_app(components)),
        base_url="http://test",
    )
    async with client:
        session = await client.get("/api/v1/session", headers=auth())
        assert session.json()["runtime_mode"] == "demo"
    if components.historian is not None:
        await components.historian.close()
    if components.runtime is not None:
        await components.runtime.shutdown()
    await components.database.dispose()


async def test_health_is_public_but_game_api_requires_bearer_token(
    tmp_path: Path,
) -> None:
    client, database, _ = await make_client(tmp_path)
    async with client:
        assert (await client.get("/health/live")).status_code == 200
        unauthorized = await client.get("/api/v1/games")
        assert unauthorized.status_code == 401
        assert unauthorized.json()["error"]["code"] == "unauthorized"
        assert unauthorized.json()["error"]["request_id"]
        session = await client.get("/api/v1/session", headers=auth())
        assert session.json() == {
            "authenticated": True,
            "capabilities": ["control", "public_view", "god_view"],
            "runtime_mode": "openai",
            "version": "0.3.0",
        }
        assert (await client.get("/metrics")).status_code == 401
        metrics = await client.get("/metrics", headers=auth())
        assert metrics.status_code == 200
        assert "werewolf_active_games" in metrics.text
    await database.dispose()


async def test_create_start_and_duplicate_start_contract(tmp_path: Path) -> None:
    client, database, _ = await make_client(tmp_path)
    async with client:
        created = await client.post(
            "/api/v1/games", json={"player_count": 6}, headers=auth()
        )
        assert created.status_code == 201
        game_id = created.json()["id"]
        started = await client.post(f"/api/v1/games/{game_id}/start", headers=auth())
        assert started.status_code == 202
        duplicate = await client.post(f"/api/v1/games/{game_id}/start", headers=auth())
        assert duplicate.status_code == 409
        assert duplicate.json()["error"]["code"] == "game_already_started"
    await database.dispose()


async def test_event_views_and_terminal_sse_replay(tmp_path: Path) -> None:
    client, database, repository = await make_client(tmp_path)
    game = GameState(
        id="game-events", player_count=6, status=GameStatus.DRAW, phase=Phase.FINISHED
    )
    await repository.create_game(game)
    public = GameEvent(
        "game-events",
        0,
        "day_started",
        Phase.DAY,
        Visibility.PUBLIC,
        (),
        {"round": 1},
    )
    private = GameEvent(
        "game-events",
        0,
        "identity_assigned",
        Phase.SETUP,
        Visibility.PRIVATE,
        ("刘备",),
        {"player": "刘备", "role": "狼人"},
    )
    await repository.append_event(public)
    await repository.append_event(private)

    async with client:
        public_response = await client.get(
            "/api/v1/games/game-events/events", headers=auth()
        )
        assert [event["type"] for event in public_response.json()] == ["day_started"]
        god_response = await client.get(
            "/api/v1/games/game-events/events?view=god", headers=auth()
        )
        assert [event["type"] for event in god_response.json()] == [
            "day_started",
            "identity_assigned",
        ]
        stream = await client.get(
            "/api/v1/games/game-events/stream",
            headers={**auth(), "Last-Event-ID": "0"},
        )
        assert stream.status_code == 200
        assert "id: 1" in stream.text
        assert "event: day_started" in stream.text
        assert "identity_assigned" not in stream.text
    await database.dispose()


async def test_running_sse_emits_comment_heartbeat_without_persisting_event(
    tmp_path: Path, monkeypatch
) -> None:
    _, database, repository = await make_client(tmp_path)
    game = GameState(
        id="running-heartbeat",
        player_count=6,
        status=GameStatus.RUNNING,
        phase=Phase.DAY,
    )
    await repository.create_game(game)
    broker = EventBroker()
    components = SimpleNamespace(repository=repository, broker=broker)
    observed_timeouts: list[float | None] = []

    async def emit_timeout(_future, **kwargs):
        observed_timeouts.append(kwargs.get("timeout"))
        raise TimeoutError

    monkeypatch.setattr(api_app.asyncio, "wait_for", emit_timeout)
    stream = api_app._event_stream(components, game, 0, False)
    try:
        assert await anext(stream) == ": keep-alive\n\n"
    finally:
        await stream.aclose()

    assert observed_timeouts == [15]
    assert await repository.list_events(game.id, 0, include_private=True) == []
    await database.dispose()


async def test_running_sse_emits_transient_speech_without_event_id(
    tmp_path: Path,
) -> None:
    _, database, repository = await make_client(tmp_path)
    game = GameState(
        id="running-stream",
        player_count=6,
        status=GameStatus.RUNNING,
        phase=Phase.DAY,
    )
    await repository.create_game(game)
    broker = EventBroker()
    components = SimpleNamespace(repository=repository, broker=broker)
    stream = api_app._event_stream(components, game, 0, False)
    frame_task = asyncio.create_task(anext(stream))
    for _ in range(20):
        if broker._subscribers.get(game.id):
            break
        await asyncio.sleep(0.01)
    await broker.publish(
        TransientGameEvent(
            game_id=game.id,
            type="speech_delta",
            phase=Phase.DAY,
            visibility=Visibility.PUBLIC,
            recipients=(),
            payload={"player": "刘备", "content_so_far": "曹操可疑"},
        )
    )
    try:
        frame = await asyncio.wait_for(frame_task, 0.5)
        assert frame.startswith("event: speech_delta\n")
        assert "id:" not in frame
        assert "曹操可疑" in frame
        assert await repository.list_events(game.id, 0, True) == []
    finally:
        await stream.aclose()
        await database.dispose()


async def test_validation_errors_use_stable_error_shape(tmp_path: Path) -> None:
    client, database, _ = await make_client(tmp_path)
    async with client:
        response = await client.post(
            "/api/v1/games", json={"player_count": 5}, headers=auth()
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_error"
    await database.dispose()


async def test_game_views_readiness_and_not_found_errors(tmp_path: Path) -> None:
    client, database, repository = await make_client(tmp_path)
    game = GameState(
        id="views",
        player_count=6,
        players=[GamePlayer("刘备", "刘备", "狼人")],
    )
    await repository.create_game(game)
    async with client:
        ready = await client.get("/health/ready")
        assert ready.status_code == 200
        public = await client.get("/api/v1/games/views", headers=auth())
        god = await client.get("/api/v1/games/views?view=god", headers=auth())
        assert "role" not in public.json()["players"][0]
        assert god.json()["players"][0]["role"] == "狼人"
        listed = await client.get("/api/v1/games", headers=auth())
        assert listed.json()[0]["id"] == "views"
        missing = await client.get("/api/v1/games/missing", headers=auth())
        assert missing.status_code == 404
        invalid_sse = await client.get(
            "/api/v1/games/views/stream",
            headers={**auth(), "Last-Event-ID": "bad"},
        )
        assert invalid_sse.status_code == 422
        assert invalid_sse.json()["error"]["code"] == "invalid_last_event_id"
    await database.dispose()


async def test_terminal_public_view_reveals_roles_but_cancelled_game_does_not(
    tmp_path: Path,
) -> None:
    client, database, repository = await make_client(tmp_path)
    completed = GameState(
        id="completed",
        player_count=6,
        status=GameStatus.COMPLETED,
        phase=Phase.FINISHED,
        players=[GamePlayer("曹操", "曹操", "狼人")],
    )
    cancelled = GameState(
        id="cancelled",
        player_count=6,
        status=GameStatus.CANCELLED,
        phase=Phase.FINISHED,
        players=[GamePlayer("刘备", "刘备", "预言家")],
    )
    await repository.create_game(completed)
    await repository.create_game(cancelled)
    async with client:
        revealed = await client.get("/api/v1/games/completed", headers=auth())
        hidden = await client.get("/api/v1/games/cancelled", headers=auth())
        assert revealed.json()["players"][0]["role"] == "狼人"
        assert "role" not in hidden.json()["players"][0]
    await database.dispose()


async def test_openapi_exposes_typed_session_game_and_event_contracts(
    tmp_path: Path,
) -> None:
    client, database, _ = await make_client(tmp_path)
    async with client:
        schema = (await client.get("/openapi.json")).json()
        components = schema["components"]["schemas"]
        assert {
            "SessionResponse",
            "GameResponse",
            "EventResponse",
            "GameReviewResponse",
            "SpeechStreamFrameResponse",
        } <= set(components)
        event_schema = components["EventResponse"]
        assert event_schema["discriminator"]["propertyName"] == "type"
        mapping = event_schema["discriminator"]["mapping"]
        assert mapping["speech"].endswith("/SpeechEvent")
        assert mapping["roles_revealed"].endswith("/RolesRevealedEvent")
        assert mapping["speech_moderated"].endswith("/LegacyModeratedSpeechEvent")
        speech_payload = components["SpeechEvent"]["properties"]["payload"]
        assert speech_payload == {"$ref": "#/components/schemas/SpeechPayload"}
        assert "delete" in schema["paths"]["/api/v1/games/{game_id}"]
    await database.dispose()


async def test_delete_terminal_game_removes_events_and_review(tmp_path: Path) -> None:
    client, database, repository = await make_client(tmp_path)
    game = GameState(
        id="deletable",
        player_count=6,
        status=GameStatus.COMPLETED,
        phase=Phase.FINISHED,
    )
    await repository.create_game(game)
    await repository.append_event(
        GameEvent(
            game.id,
            0,
            "game_finished",
            Phase.FINISHED,
            Visibility.PUBLIC,
            (),
            {"winner": "villagers"},
        )
    )

    async with client:
        unauthorized = await client.delete(f"/api/v1/games/{game.id}")
        assert unauthorized.status_code == 401
        deleted = await client.delete(f"/api/v1/games/{game.id}", headers=auth())
        assert deleted.status_code == 204
        assert not deleted.content
        snapshot = await client.get(f"/api/v1/games/{game.id}", headers=auth())
        assert snapshot.status_code == 404
        assert (
            await client.get(f"/api/v1/games/{game.id}/events", headers=auth())
        ).status_code == 404
        assert (
            await client.get(f"/api/v1/games/{game.id}/review", headers=auth())
        ).status_code == 404
        repeated = await client.delete(f"/api/v1/games/{game.id}", headers=auth())
        assert repeated.status_code == 404
    await database.dispose()


async def test_delete_rejects_running_game_and_pending_review(tmp_path: Path) -> None:
    client, database, repository = await make_client(tmp_path)
    running = GameState(id="running-delete", player_count=6, status=GameStatus.RUNNING)
    review_pending = GameState(
        id="pending-review-delete",
        player_count=6,
        status=GameStatus.DRAW,
        phase=Phase.FINISHED,
    )
    await repository.create_game(running)
    await repository.create_game(review_pending)
    await repository.create_review(GameReview(game_id=review_pending.id))

    async with client:
        rejected = await client.delete(f"/api/v1/games/{running.id}", headers=auth())
        assert rejected.status_code == 409
        assert rejected.json()["error"]["code"] == "game_not_deletable"
        pending = await client.delete(
            f"/api/v1/games/{review_pending.id}", headers=auth()
        )
        assert pending.status_code == 409
        assert pending.json()["error"]["code"] == "review_in_progress"
    await database.dispose()


async def test_review_creation_and_delete_are_serialized(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'serialized.db'}")
    await database.create_schema()
    repository = SqliteGameRepository(database.session_factory)
    game = GameState(
        id="serialized",
        player_count=6,
        status=GameStatus.COMPLETED,
        phase=Phase.FINISHED,
    )
    await repository.create_game(game)
    operation_locks = GameOperationLocks()
    service = GameService(
        repository,
        lambda: InstantEngine(),
        max_concurrent_games=1,
        operation_locks=operation_locks,
    )

    class WaitingHistorian:
        async def generate_review(self, dossier: GameDossier) -> GameReviewResult:
            await asyncio.Event().wait()
            raise AssertionError("unreachable")

    review_service = GameReviewService(
        repository,
        WaitingHistorian(),
        operation_locks=operation_locks,
    )
    create_started = asyncio.Event()
    release_create = asyncio.Event()
    original_create = repository.create_review

    async def delayed_create(review: GameReview) -> GameReview:
        create_started.set()
        await release_create.wait()
        return await original_create(review)

    monkeypatch.setattr(repository, "create_review", delayed_create)
    review_request = asyncio.create_task(review_service.request_review(game.id))
    await create_started.wait()
    delete_request = asyncio.create_task(service.delete_game(game.id))
    await asyncio.sleep(0)
    assert not delete_request.done()

    release_create.set()
    assert (await review_request).status.value == "pending"
    with pytest.raises(ConflictError) as error:
        await delete_request
    assert error.value.code == "review_in_progress"
    assert await repository.get_game(game.id) is not None

    await review_service.shutdown()
    await database.dispose()
    await database.dispose()


async def test_completed_game_can_generate_and_reuse_historian_review(
    tmp_path: Path,
) -> None:
    client, database, repository = await make_client(tmp_path)
    game = GameState(
        id="review-api",
        player_count=2,
        status=GameStatus.COMPLETED,
        phase=Phase.FINISHED,
        winner="villagers",
        players=[
            GamePlayer("刘备", "刘备", "预言家", persona_tags=["仁厚沉稳"]),
            GamePlayer("曹操", "曹操", "狼人", is_alive=False),
        ],
    )
    await repository.create_game(game)
    FakeHistorian.last_dossier = None
    await repository.append_event(
        GameEvent(
            game.id,
            0,
            "speech",
            Phase.FINISHED,
            Visibility.PUBLIC,
            (),
            {
                "player": "刘备",
                "content": "曹操可疑",
                "stream_trace": [{"offset_ms": 0, "delta": "曹操可疑"}],
            },
        )
    )

    async with client:
        missing = await client.get(f"/api/v1/games/{game.id}/review", headers=auth())
        assert missing.status_code == 404
        started = await client.post(
            f"/api/v1/games/{game.id}/review",
            headers=auth(),
        )
        assert started.status_code == 202
        assert started.json()["status"] == "pending"
        for _ in range(20):
            completed = await client.get(
                f"/api/v1/games/{game.id}/review",
                headers=auth(),
            )
            if completed.json()["status"] == "completed":
                break
            await asyncio.sleep(0.01)

        assert FakeHistorian.last_dossier is not None
        assert "stream_trace" not in FakeHistorian.last_dossier.events[0].payload
        assert completed.json()["result"]["mvp"] == "刘备"
        assert completed.json()["result"]["player_reviews"][0]["score"] == 8.0
        reused = await client.post(
            f"/api/v1/games/{game.id}/review",
            headers=auth(),
        )
        assert reused.json()["status"] == "completed"
        snapshot = await client.get(f"/api/v1/games/{game.id}", headers=auth())
        assert snapshot.json()["players"][0]["persona_tags"] == ["仁厚沉稳"]
    await database.dispose()


async def test_built_spa_is_served_without_shadowing_api(tmp_path: Path) -> None:
    dist = tmp_path / "web"
    dist.mkdir()
    (dist / "index.html").write_text("<h1>群雄夜宴</h1>", encoding="utf-8")
    settings = Settings(
        llm_api_key="test-key",
        llm_model_id="offline",
        llm_base_url="http://model.invalid/v1",
        app_api_token=TOKEN,
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'web.db'}",
        web_dist_dir=str(dist),
    )
    database = Database(settings.database_url)
    await database.create_schema()
    repository = SqliteGameRepository(database.session_factory)
    broker = EventBroker()
    service = GameService(repository, lambda: InstantEngine(), max_concurrent_games=1)
    app = create_app(AppComponents(settings, database, repository, broker, service))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        root = await client.get("/")
        nested = await client.get("/games/example")
        health = await client.get("/health/live")
        assert "群雄夜宴" in root.text
        assert nested.text == root.text
        assert health.json() == {"status": "ok"}
    await database.dispose()
