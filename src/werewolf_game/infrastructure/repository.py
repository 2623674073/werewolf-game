from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from werewolf_game.domain.models import (
    GameEvent,
    GamePlayer,
    GameState,
    GameStatus,
    Phase,
    Visibility,
)
from werewolf_game.infrastructure.orm import EventRow, GameRow


class SqliteGameRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def create_game(self, game: GameState) -> GameState:
        async with self.session_factory() as session:
            session.add(_game_to_row(game))
            await session.commit()
        return game

    async def get_game(self, game_id: str) -> GameState | None:
        async with self.session_factory() as session:
            row = await session.get(GameRow, game_id)
            return _row_to_game(row) if row is not None else None

    async def list_games(self, offset: int, limit: int) -> list[GameState]:
        async with self.session_factory() as session:
            rows = (
                await session.scalars(
                    select(GameRow)
                    .order_by(GameRow.created_at.desc())
                    .offset(offset)
                    .limit(limit)
                )
            ).all()
            return [_row_to_game(row) for row in rows]

    async def save_game(self, game: GameState) -> None:
        values = _game_values(game)
        async with self.session_factory() as session:
            await session.execute(
                update(GameRow).where(GameRow.id == game.id).values(**values)
            )
            await session.commit()

    async def append_event(self, event: GameEvent) -> GameEvent:
        async with self.session_factory() as session:
            last_seq = await session.scalar(
                select(func.max(EventRow.seq)).where(EventRow.game_id == event.game_id)
            )
            stored = GameEvent(
                game_id=event.game_id,
                seq=(last_seq or 0) + 1,
                type=event.type,
                phase=event.phase,
                visibility=event.visibility,
                recipients=event.recipients,
                payload=event.payload,
                created_at=event.created_at,
            )
            session.add(
                EventRow(
                    game_id=stored.game_id,
                    seq=stored.seq,
                    type=stored.type,
                    phase=stored.phase.value,
                    visibility=stored.visibility.value,
                    recipients=list(stored.recipients),
                    payload=stored.payload,
                    created_at=stored.created_at,
                )
            )
            await session.commit()
            return stored

    async def list_events(
        self,
        game_id: str,
        after_seq: int,
        include_private: bool,
    ) -> list[GameEvent]:
        query = (
            select(EventRow)
            .where(EventRow.game_id == game_id, EventRow.seq > after_seq)
            .order_by(EventRow.seq)
        )
        if not include_private:
            query = query.where(EventRow.visibility == Visibility.PUBLIC.value)
        async with self.session_factory() as session:
            rows = (await session.scalars(query)).all()
            return [_row_to_event(row) for row in rows]

    async def mark_running_interrupted(self) -> int:
        async with self.session_factory() as session:
            result = await session.execute(
                update(GameRow)
                .where(GameRow.status == GameStatus.RUNNING.value)
                .values(
                    status=GameStatus.INTERRUPTED.value,
                    phase=Phase.FINISHED.value,
                    finished_at=datetime.now(UTC),
                    error_code="service_restarted",
                )
            )
            await session.commit()
            return int(result.rowcount or 0)  # type: ignore[attr-defined]

    async def ping(self) -> bool:
        async with self.session_factory() as session:
            value = cast(int | None, await session.scalar(select(1)))
            return value == 1


def _players_to_json(players: list[GamePlayer]) -> list[dict[str, object]]:
    return [
        {
            "name": player.name,
            "character": player.character,
            "role": player.role,
            "is_alive": player.is_alive,
            "has_antidote": player.has_antidote,
            "has_poison": player.has_poison,
        }
        for player in players
    ]


def _game_values(game: GameState) -> dict[str, object]:
    return {
        "player_count": game.player_count,
        "status": game.status.value,
        "phase": game.phase.value,
        "round_number": game.round_number,
        "players": _players_to_json(game.players),
        "winner": game.winner,
        "error_code": game.error_code,
        "created_at": game.created_at,
        "started_at": game.started_at,
        "finished_at": game.finished_at,
    }


def _game_to_row(game: GameState) -> GameRow:
    return GameRow(id=game.id, **_game_values(game))


def _row_to_game(row: GameRow) -> GameState:
    return GameState(
        id=row.id,
        player_count=row.player_count,
        status=GameStatus(row.status),
        phase=Phase(row.phase),
        round_number=row.round_number,
        players=[GamePlayer(**data) for data in row.players],
        winner=row.winner,
        error_code=row.error_code,
        created_at=row.created_at,
        started_at=row.started_at,
        finished_at=row.finished_at,
    )


def _row_to_event(row: EventRow) -> GameEvent:
    return GameEvent(
        game_id=row.game_id,
        seq=row.seq,
        type=row.type,
        phase=Phase(row.phase),
        visibility=Visibility(row.visibility),
        recipients=tuple(row.recipients),
        payload=row.payload,
        created_at=row.created_at,
    )
