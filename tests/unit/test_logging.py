import json
import logging

from werewolf_game.infrastructure.logging import JsonFormatter


def test_json_formatter_includes_correlation_fields_without_secrets() -> None:
    record = logging.LogRecord(
        "werewolf", logging.INFO, __file__, 1, "event persisted", (), None
    )
    record.request_id = "request-1"
    record.game_id = "game-1"
    record.phase = "night"
    record.event_type = "night_started"
    payload = json.loads(JsonFormatter().format(record))
    assert payload["request_id"] == "request-1"
    assert payload["game_id"] == "game-1"
    assert payload["event_type"] == "night_started"
    assert "api_key" not in payload
