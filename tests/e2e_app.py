from __future__ import annotations

import asyncio
import atexit
import os
from datetime import UTC, datetime
from pathlib import Path
from tempfile import gettempdir

from werewolf_game.api.app import AppComponents, create_app
from werewolf_game.application.events import EventBroker, EventCoordinator
from werewolf_game.application.service import GameService
from werewolf_game.config import Settings
from werewolf_game.domain.models import (
    GamePlayer,
    GameState,
    GameStatus,
    Phase,
    Visibility,
)
from werewolf_game.infrastructure.database import Database
from werewolf_game.infrastructure.repository import SqliteGameRepository

TOKEN = "e2e-token-at-least-24-characters"
E2E_DB_PATH = Path(gettempdir()) / f"werewolf-e2e-{os.getpid()}.db"
atexit.register(lambda: E2E_DB_PATH.unlink(missing_ok=True))


class DemoEngine:
    def __init__(
        self,
        repository: SqliteGameRepository,
        events: EventCoordinator,
    ) -> None:
        self.repository = repository
        self.events = events

    async def run(self, game: GameState) -> None:
        roster = [
            GamePlayer("刘备", "刘备", "预言家"),
            GamePlayer("关羽", "关羽", "村民"),
            GamePlayer("张飞", "张飞", "村民"),
            GamePlayer("诸葛亮", "诸葛亮", "女巫"),
            GamePlayer("赵云", "赵云", "村民"),
            GamePlayer("曹操", "曹操", "狼人"),
            GamePlayer("孙权", "孙权", "狼人"),
            GamePlayer("司马懿", "司马懿", "狼人"),
            GamePlayer("周瑜", "周瑜", "猎人"),
            GamePlayer("吕布", "吕布", "村民"),
            GamePlayer("貂蝉", "貂蝉", "村民"),
            GamePlayer("陆逊", "陆逊", "村民"),
        ]
        game.players = roster[: game.player_count]
        game.status = GameStatus.RUNNING
        game.phase = Phase.SETUP
        game.started_at = datetime.now(UTC)
        await self.repository.save_game(game)
        for player in game.players:
            await self.events.emit(
                game,
                "identity_assigned",
                {"player": player.name, "role": player.role},
                visibility=Visibility.PRIVATE,
                recipients=[player.name],
            )
        await self.events.emit(
            game,
            "game_started",
            {"players": [player.name for player in game.players]},
        )
        game.phase = Phase.DAY
        game.round_number = 1
        await self.repository.save_game(game)
        await self.events.emit(game, "day_started", {"round": 1})
        await self.events.emit(
            game,
            "discussion_started",
            {
                "discussion_kind": "day",
                "round": 1,
                "participants": [player.name for player in game.players],
            },
        )
        for index, player in enumerate(game.players[:3], start=1):
            await self.events.emit(
                game,
                "speaker_turn_started",
                {
                    "player": player.name,
                    "round": 1,
                    "discussion_round": 1,
                    "discussion_kind": "day",
                },
            )
            await asyncio.sleep(0.04)
            await self.events.emit(
                game,
                "speech",
                {
                    "player": player.name,
                    "content": f"第{index}席发言：我认为曹操的逻辑值得继续追问。",
                    "round": 1,
                    "discussion_round": 1,
                    "discussion_kind": "day",
                },
            )
        await self.events.emit(
            game,
            "day_vote",
            {
                "player": "刘备",
                "vote": "曹操",
                "reason": "发言前后矛盾",
                "suspicion_level": 9,
            },
            visibility=Visibility.PRIVATE,
            recipients=["刘备"],
        )
        next(player for player in game.players if player.name == "曹操").eliminate()
        await self.repository.save_game(game)
        await self.events.emit(
            game,
            "vote_result",
            {"voted_out": "曹操", "votes": 5, "hunter_shot": None},
        )
        game.status = GameStatus.COMPLETED
        game.phase = Phase.FINISHED
        game.winner = "villagers"
        game.finished_at = datetime.now(UTC)
        await self.repository.save_game(game)
        await self.events.emit(
            game,
            "roles_revealed",
            {
                "players": [
                    {"player": player.name, "role": player.role}
                    for player in game.players
                ]
            },
        )
        await self.events.emit(game, "game_finished", {"winner": "villagers"})
        await self.events.broker.close_game(game.id)


settings = Settings(
    llm_api_key="e2e-model-key",
    llm_model_id="offline-e2e",
    llm_base_url="http://offline.invalid/v1",
    app_api_token=TOKEN,
    database_url=f"sqlite+aiosqlite:///{E2E_DB_PATH.as_posix()}",
    web_dist_dir="frontend/dist",
)
database = Database(settings.database_url)
asyncio.run(database.create_schema())
repository = SqliteGameRepository(database.session_factory)
broker = EventBroker()
events = EventCoordinator(repository, broker)
service = GameService(
    repository,
    lambda: DemoEngine(repository, events),
    max_concurrent_games=2,
    events=events,
)
app = create_app(AppComponents(settings, database, repository, broker, service))
