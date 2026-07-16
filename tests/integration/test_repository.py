from __future__ import annotations

from pathlib import Path

from sqlalchemy import text

from werewolf_game.domain.models import (
    GameEvent,
    GameState,
    GameStatus,
    Phase,
    Visibility,
)
from werewolf_game.domain.reviews import GameReview, ReviewStatus
from werewolf_game.infrastructure.database import Database
from werewolf_game.infrastructure.repository import SqliteGameRepository


async def test_sqlite_repository_round_trips_state_and_filters_events(
    tmp_path: Path,
) -> None:
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'game.db'}")
    await database.create_schema()
    repository = SqliteGameRepository(database.session_factory)
    game = GameState(id="game-1", player_count=6)
    await repository.create_game(game)

    public = await repository.append_event(
        GameEvent("game-1", 0, "public", Phase.DAY, Visibility.PUBLIC, (), {"x": 1})
    )
    private = await repository.append_event(
        GameEvent(
            "game-1",
            0,
            "private",
            Phase.NIGHT,
            Visibility.PRIVATE,
            ("刘备",),
            {"role": "狼人"},
        )
    )

    assert (public.seq, private.seq) == (1, 2)
    assert [
        event.type for event in await repository.list_events("game-1", 0, False)
    ] == ["public"]
    assert [
        event.type for event in await repository.list_events("game-1", 1, True)
    ] == ["private"]
    loaded = await repository.get_game("game-1")
    assert loaded is not None and loaded.player_count == 6

    async with database.engine.connect() as connection:
        mode = await connection.scalar(text("PRAGMA journal_mode"))
    assert str(mode).lower() == "wal"
    await database.dispose()


async def test_startup_marks_running_games_interrupted(tmp_path: Path) -> None:
    database_path = tmp_path / "nested" / "game.db"
    database = Database(f"sqlite+aiosqlite:///{database_path}")
    await database.create_schema()
    assert database_path.exists()
    repository = SqliteGameRepository(database.session_factory)
    game = GameState(id="running", player_count=6, status=GameStatus.RUNNING)
    await repository.create_game(game)

    assert await repository.mark_running_interrupted() == 1
    loaded = await repository.get_game("running")
    assert loaded is not None
    assert loaded.status is GameStatus.INTERRUPTED
    assert loaded.phase is Phase.FINISHED
    await database.dispose()


async def test_repository_persists_reviews_and_marks_stale_pending(
    tmp_path: Path,
) -> None:
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'reviews.db'}")
    await database.create_schema()
    repository = SqliteGameRepository(database.session_factory)
    await repository.create_game(
        GameState(id="reviewed", player_count=6, status=GameStatus.DRAW)
    )
    await repository.create_review(GameReview(game_id="reviewed"))

    loaded = await repository.get_review("reviewed")
    assert loaded is not None and loaded.status is ReviewStatus.PENDING
    assert await repository.mark_pending_reviews_failed("service_restarted") == 1
    failed = await repository.get_review("reviewed")
    assert failed is not None
    assert failed.status is ReviewStatus.FAILED
    assert failed.error_code == "service_restarted"
    await database.dispose()


async def test_delete_game_cascades_events_and_review(tmp_path: Path) -> None:
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'delete.db'}")
    await database.create_schema()
    repository = SqliteGameRepository(database.session_factory)
    game = GameState(id="delete-me", player_count=6, status=GameStatus.COMPLETED)
    await repository.create_game(game)
    await repository.append_event(
        GameEvent(
            game.id,
            0,
            "game_finished",
            Phase.FINISHED,
            Visibility.PUBLIC,
            (),
            {},
        )
    )
    await repository.create_review(GameReview(game_id=game.id))

    assert await repository.delete_game(game.id) is True
    assert await repository.delete_game(game.id) is False
    assert await repository.get_game(game.id) is None
    assert await repository.list_events(game.id, 0, True) == []
    assert await repository.get_review(game.id) is None

    async with database.engine.connect() as connection:
        foreign_keys = await connection.execute(
            text("PRAGMA foreign_key_list(game_events)")
        )
        assert any(row[2] == "games" and row[6] == "CASCADE" for row in foreign_keys)
    await database.dispose()
