from __future__ import annotations

import argparse
import asyncio
from collections.abc import Sequence
from uuid import uuid4

import uvicorn

from werewolf_game.application.engine import GameEngine
from werewolf_game.application.events import EventBroker, EventCoordinator
from werewolf_game.config import Settings
from werewolf_game.console import ConsolePresenter
from werewolf_game.domain.models import GameState
from werewolf_game.infrastructure.agentscope_runtime import (
    AgentScopeRuntime,
    build_openai_compatible_model,
)
from werewolf_game.infrastructure.database import Database
from werewolf_game.infrastructure.logging import configure_logging
from werewolf_game.infrastructure.moderation import McpSpeechModerator
from werewolf_game.infrastructure.repository import SqliteGameRepository


def build_server_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="启动狼人杀 HTTP API")
    parser.add_argument("--host", help="监听地址，默认读取 HOST")
    parser.add_argument("--port", type=int, help="监听端口，默认读取 PORT")
    parser.add_argument("--reload", action="store_true", help="启用开发热重载")
    return parser


def build_game_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="狼人杀命令行工具")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run", help="运行一局 AI 狼人杀")
    run.add_argument("--players", type=int, default=6, choices=range(6, 13))
    run.add_argument("--show-dialogue", action="store_true", help="显示可读游戏对话")
    run.add_argument(
        "--view",
        choices=("public", "god"),
        default="public",
        help="对话视角：public 公开信息，god 全知信息",
    )
    return parser


def server_main(argv: Sequence[str] | None = None) -> None:
    args = build_server_parser().parse_args(argv)
    settings = Settings()  # type: ignore[call-arg]
    configure_logging(settings.log_level)
    _print_effective_model(settings)
    uvicorn.run(
        "werewolf_game.api.app:create_app",
        factory=True,
        host=args.host or settings.host,
        port=args.port or settings.port,
        reload=args.reload,
        log_config=None,
    )


def game_main(argv: Sequence[str] | None = None) -> None:
    args = build_game_parser().parse_args(argv)
    if args.command == "run":
        raise SystemExit(
            asyncio.run(
                _run_game(
                    args.players,
                    show_dialogue=args.show_dialogue,
                    view=args.view,
                )
            )
        )


async def _run_game(
    player_count: int,
    *,
    show_dialogue: bool = False,
    view: str = "public",
) -> int:
    settings = Settings()  # type: ignore[call-arg]
    configure_logging("WARNING" if show_dialogue else settings.log_level)
    _print_effective_model(settings)
    database = Database(settings.database_url)
    await database.create_schema()
    repository = SqliteGameRepository(database.session_factory)
    model = build_openai_compatible_model(
        api_key=settings.llm_api_key.get_secret_value(),
        model_name=settings.llm_model_id,
        base_url=settings.llm_base_url,
        timeout_seconds=settings.llm_timeout,
        max_retries=settings.model_max_retries,
    )
    runtime = AgentScopeRuntime(
        model=model,
        max_model_concurrency=settings.max_model_concurrency,
        timeout_seconds=settings.llm_timeout,
        max_retries=0,
    )
    broker = EventBroker()
    events = EventCoordinator(repository, broker)
    moderator = McpSpeechModerator(execution_timeout=settings.llm_timeout + 5)
    await moderator.start()
    game = GameState(id=str(uuid4()), player_count=player_count)
    await repository.create_game(game)
    presenter_task: asyncio.Task[None] | None = None
    if show_dialogue:
        presenter = ConsolePresenter()
        presenter_task = asyncio.create_task(
            presenter.consume(broker.subscribe(game.id, include_private=view == "god"))
        )
        await asyncio.sleep(0)
    try:
        await GameEngine(runtime, repository, events, moderator).run(game)
        if presenter_task is not None:
            await presenter_task
        print(f"游戏结束：{game.winner or game.status.value}")
        return 0 if game.error_code is None else 1
    finally:
        if presenter_task is not None and not presenter_task.done():
            presenter_task.cancel()
        await moderator.close()
        await database.dispose()


def _print_effective_model(settings: Settings) -> None:
    key = settings.llm_api_key.get_secret_value()
    suffix = key[-4:] if len(key) >= 4 else ""
    print(f"模型：{settings.llm_model_id}")
    print(f"Base URL：{settings.llm_base_url}")
    print(f"API Key：***{suffix}")
