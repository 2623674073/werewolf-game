from __future__ import annotations

import argparse
import asyncio
from collections.abc import Sequence
from pathlib import Path
from tempfile import NamedTemporaryFile
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
from werewolf_game.infrastructure.demo import DemoAgentRuntime
from werewolf_game.infrastructure.logging import configure_logging
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
    doctor = subparsers.add_parser("doctor", help="检查本地配置与运行环境")
    doctor.add_argument(
        "--live-model",
        action="store_true",
        help="实际调用模型验证流式与结构化输出",
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
        reload_dirs=["src"] if args.reload else None,
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
    if args.command == "doctor":
        raise SystemExit(asyncio.run(_run_doctor(live_model=args.live_model)))


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
    runtime = _build_runtime(settings)
    broker = EventBroker()
    events = EventCoordinator(repository, broker)
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
        await GameEngine(runtime, repository, events).run(game)
        if presenter_task is not None:
            await presenter_task
        print(f"游戏结束：{game.winner or game.status.value}")
        return 0 if game.error_code is None else 1
    finally:
        if presenter_task is not None and not presenter_task.done():
            presenter_task.cancel()
        await runtime.shutdown()
        await database.dispose()


def _print_effective_model(settings: Settings) -> None:
    print(f"运行模式：{settings.runtime_mode}")
    if settings.runtime_mode == "demo":
        print("模型：离线确定性 Runtime（不会调用外部服务）")
        return
    assert settings.llm_api_key is not None
    key = settings.llm_api_key.get_secret_value()
    suffix = key[-4:] if len(key) >= 4 else ""
    print(f"模型：{settings.llm_model_id}")
    print(f"Base URL：{settings.llm_base_url}")
    print(f"API Key：***{suffix}")


def _build_runtime(settings: Settings) -> AgentScopeRuntime | DemoAgentRuntime:
    if settings.runtime_mode == "demo":
        return DemoAgentRuntime()
    assert settings.llm_api_key is not None
    assert settings.llm_model_id is not None
    assert settings.llm_base_url is not None
    dialogue_model = build_openai_compatible_model(
        api_key=settings.llm_api_key.get_secret_value(),
        model_name=settings.llm_model_id,
        base_url=settings.llm_base_url,
        timeout_seconds=settings.llm_timeout,
        max_retries=settings.model_max_retries,
        stream=True,
        trust_env=settings.llm_trust_env,
    )
    decision_model = build_openai_compatible_model(
        api_key=settings.llm_api_key.get_secret_value(),
        model_name=settings.llm_model_id,
        base_url=settings.llm_base_url,
        timeout_seconds=settings.llm_timeout,
        max_retries=settings.model_max_retries,
        trust_env=settings.llm_trust_env,
    )
    return AgentScopeRuntime(
        model=dialogue_model,
        decision_model=decision_model,
        max_model_concurrency=settings.max_model_concurrency,
        timeout_seconds=settings.llm_timeout,
        max_retries=0,
    )


async def _run_doctor(*, live_model: bool) -> int:
    from werewolf_game.domain.models import GamePlayer
    from werewolf_game.domain.schemas import vote_model

    settings = Settings()  # type: ignore[call-arg]
    _print_effective_model(settings)
    failures: list[str] = []
    database = Database(settings.database_url)
    try:
        if await SqliteGameRepository(database.session_factory).ping():
            print("[OK] 数据库连接")
        else:
            failures.append("数据库连接失败")
    except Exception:
        failures.append("数据库连接失败")
    finally:
        await database.dispose()

    dist = Path(settings.web_dist_dir)
    if (dist / "index.html").is_file():
        print("[OK] 前端构建产物")
    else:
        failures.append(f"未找到前端构建：{dist / 'index.html'}")

    database_path = Path("data")
    try:
        await asyncio.to_thread(_check_writable_directory, database_path)
        print("[OK] 数据目录可写")
    except OSError:
        failures.append("数据目录不可写")

    if live_model:
        runtime = _build_runtime(settings)
        game = GameState(id="doctor", player_count=1)
        game.players = [GamePlayer("诊断席", "刘备", "村民")]
        try:
            await runtime.setup(game, {"诊断席": "你正在执行连接诊断，请简短回复。"})
            try:
                activities = [
                    item
                    async for item in runtime.discuss(
                        game.id, ["诊断席"], "请回复连接正常", 1
                    )
                ]
                if not any(item.kind == "speech_completed" for item in activities):
                    raise RuntimeError("未收到完整回复")
                print("[OK] 模型流式回复")
            except Exception:
                failures.append("模型流式回复验证失败")

            try:
                decision = await runtime.decide(
                    game.id,
                    "诊断席",
                    "请选择诊断目标",
                    vote_model(["诊断目标"]),
                )
                if decision is None:
                    raise RuntimeError("未收到结构化输出")
                print("[OK] 模型结构化输出")
            except Exception:
                failures.append("模型结构化输出验证失败")
        except Exception:
            failures.append("模型会话初始化失败")
        finally:
            await runtime.close(game.id)
            await runtime.shutdown()
    else:
        print("[SKIP] 模型调用（使用 --live-model 启用）")

    for failure in failures:
        print(f"[FAIL] {failure}")
    return 1 if failures else 0


def _check_writable_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=path, prefix="doctor-", delete=True):
        pass
