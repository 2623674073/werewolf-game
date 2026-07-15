from __future__ import annotations

from pathlib import Path

from httpx import ASGITransport, AsyncClient

from werewolf_game.api.app import AppComponents, create_app
from werewolf_game.application.events import EventBroker
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
from werewolf_game.infrastructure.database import Database
from werewolf_game.infrastructure.repository import SqliteGameRepository

TOKEN = "test-token-with-at-least-24-chars"


class InstantEngine:
    async def run(self, game: GameState) -> None:
        game.status = GameStatus.DRAW
        game.phase = Phase.FINISHED
        game.winner = "draw"


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
    service = GameService(repository, lambda: InstantEngine(), max_concurrent_games=2)
    app = create_app(AppComponents(settings, database, repository, broker, service))
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    return client, database, repository


def auth() -> dict[str, str]:
    return {"Authorization": f"Bearer {TOKEN}"}


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
        }
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
        assert {"SessionResponse", "GameResponse", "EventResponse"} <= set(components)
        event_type = components["EventResponse"]["properties"]["type"]
        assert "speech" in event_type["enum"]
        assert "roles_revealed" in event_type["enum"]
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
