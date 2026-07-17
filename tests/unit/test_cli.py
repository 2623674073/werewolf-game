from pathlib import Path

import pytest

from werewolf_game.cli import (
    _build_runtime,
    _print_effective_model,
    _run_doctor,
    _run_game,
    build_game_parser,
    build_server_parser,
    server_main,
)
from werewolf_game.config import Settings
from werewolf_game.infrastructure.demo import DemoAgentRuntime


def test_cli_parsers_expose_serve_and_run_help() -> None:
    with pytest.raises(SystemExit) as server_exit:
        build_server_parser().parse_args(["--help"])
    with pytest.raises(SystemExit) as game_exit:
        build_game_parser().parse_args(["run", "--help"])
    assert server_exit.value.code == 0
    assert game_exit.value.code == 0


def test_game_cli_accepts_dialogue_and_view_options() -> None:
    args = build_game_parser().parse_args(
        ["run", "--players", "6", "--show-dialogue", "--view", "god"]
    )
    assert args.show_dialogue is True
    assert args.view == "god"
    doctor = build_game_parser().parse_args(["doctor", "--live-model"])
    assert doctor.live_model is True


def test_server_cli_uses_settings_without_exposing_full_key(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("LLM_API_KEY", "very-secret-key")
    monkeypatch.setenv("LLM_MODEL_ID", "deepseek-v4-flash")
    monkeypatch.setenv("LLM_BASE_URL", "http://model.example/v1")
    monkeypatch.setenv("APP_API_TOKEN", "token-with-at-least-24-characters")
    called: dict[str, object] = {}
    monkeypatch.setattr(
        "werewolf_game.cli.uvicorn.run",
        lambda *args, **kwargs: called.update(kwargs),
    )

    server_main(["--host", "0.0.0.0", "--port", "9000", "--reload"])

    output = capsys.readouterr().out
    assert "very-secret-key" not in output
    assert "-key" in output
    assert called["host"] == "0.0.0.0"
    assert called["port"] == 9000
    assert called["reload_dirs"] == ["src"]


def test_effective_model_masks_short_keys(capsys: pytest.CaptureFixture[str]) -> None:
    settings = Settings(
        llm_api_key="abc",
        llm_model_id="deepseek-v4-flash",
        llm_base_url="http://model.example/v1",
        app_api_token="token-with-at-least-24-characters",
    )
    _print_effective_model(settings)
    assert "API Key：***\n" in capsys.readouterr().out


def test_demo_runtime_builder_and_output(capsys: pytest.CaptureFixture[str]) -> None:
    settings = Settings(
        runtime_mode="demo",
        app_api_token="token-with-at-least-24-characters",
    )
    assert isinstance(_build_runtime(settings), DemoAgentRuntime)
    _print_effective_model(settings)
    output = capsys.readouterr().out
    assert "运行模式：demo" in output
    assert "不会调用外部服务" in output


async def test_doctor_checks_demo_environment_without_external_model(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (tmp_path / "frontend" / "dist").mkdir(parents=True)
    (tmp_path / "frontend" / "dist" / "index.html").write_text("ok")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("RUNTIME_MODE", "demo")
    monkeypatch.setenv("APP_API_TOKEN", "token-with-at-least-24-characters")
    monkeypatch.setenv(
        "DATABASE_URL",
        f"sqlite+aiosqlite:///{(tmp_path / 'doctor.db').as_posix()}",
    )
    monkeypatch.setenv("WEB_DIST_DIR", "frontend/dist")
    assert await _run_doctor(live_model=True) == 0
    output = capsys.readouterr().out
    assert "[OK] 数据库连接" in output
    assert "[OK] 模型流式回复" in output
    assert "[OK] 模型结构化输出" in output


async def test_cli_runs_complete_game_with_demo_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("RUNTIME_MODE", "demo")
    monkeypatch.setenv("APP_API_TOKEN", "token-with-at-least-24-characters")
    monkeypatch.setenv(
        "DATABASE_URL",
        f"sqlite+aiosqlite:///{(tmp_path / 'game.db').as_posix()}",
    )
    monkeypatch.setattr(
        "werewolf_game.cli._build_runtime",
        lambda _settings: DemoAgentRuntime(chunk_delay=0),
    )
    assert await _run_game(6) == 0
