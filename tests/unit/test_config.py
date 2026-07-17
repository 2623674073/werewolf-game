import pytest
from pydantic import ValidationError

from werewolf_game.config import EXAMPLE_APP_TOKEN, Settings


def test_settings_reject_short_api_token() -> None:
    with pytest.raises(ValidationError):
        Settings(llm_api_key="key", app_api_token="short")


def test_settings_do_not_expose_secrets() -> None:
    settings = Settings(
        llm_api_key="secret-openai-compatible-key",
        llm_model_id="deepseek-v4-flash",
        llm_base_url="http://model.example/v1",
        llm_timeout=45,
        app_api_token="token-with-at-least-24-characters",
    )
    assert "secret-openai-compatible-key" not in repr(settings)
    assert settings.llm_model_id == "deepseek-v4-flash"
    assert settings.llm_base_url == "http://model.example/v1"
    assert settings.llm_timeout == 45
    assert settings.max_concurrent_games == 4


def test_demo_settings_do_not_require_model_credentials() -> None:
    settings = Settings(
        runtime_mode="demo",
        app_api_token="token-with-at-least-24-characters",
    )
    assert settings.runtime_mode == "demo"


def test_settings_reject_example_token() -> None:
    with pytest.raises(ValidationError):
        Settings(
            runtime_mode="demo",
            app_api_token=EXAMPLE_APP_TOKEN,
        )
