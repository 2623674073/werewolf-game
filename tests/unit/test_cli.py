import pytest

from werewolf_game.cli import (
    _print_effective_model,
    build_game_parser,
    build_server_parser,
    server_main,
)
from werewolf_game.config import Settings


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
