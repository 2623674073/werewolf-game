from datetime import UTC, datetime

import pytest

from werewolf_game.console import format_event
from werewolf_game.domain.models import GameEvent, Phase, Visibility


def event(
    event_type: str,
    payload: dict[str, object],
    *,
    visibility: Visibility = Visibility.PUBLIC,
) -> GameEvent:
    return GameEvent(
        game_id="game-1",
        seq=1,
        type=event_type,
        phase=Phase.DAY,
        visibility=visibility,
        recipients=(),
        payload=payload,
        created_at=datetime.now(UTC),
    )


def test_console_formats_public_and_private_speeches() -> None:
    public = format_event(event("speech", {"player": "刘备", "content": "曹操可疑"}))
    private = format_event(
        event(
            "speech",
            {"player": "曹操", "content": "今晚击杀刘备"},
            visibility=Visibility.PRIVATE,
        )
    )
    assert public == "[发言] 刘备：曹操可疑"
    assert private == "[私密发言] 曹操：今晚击杀刘备"


def test_console_formats_phase_votes_and_skills() -> None:
    assert format_event(event("night_started", {"round": 2})) == "\n=== 第 2 夜 ==="
    assert "投给曹操" in format_event(
        event(
            "day_vote",
            {"player": "刘备", "vote": "曹操", "reason": "发言矛盾"},
            visibility=Visibility.PRIVATE,
        )
    )
    assert "使用毒药" in format_event(
        event(
            "witch_action",
            {"player": "貂蝉", "action": "使用毒药", "target_name": "曹操"},
            visibility=Visibility.PRIVATE,
        )
    )


@pytest.mark.parametrize(
    ("event_type", "payload", "expected"),
    [
        ("game_started", {"players": ["刘备", "曹操"]}, "游戏开始"),
        ("identity_assigned", {"player": "曹操", "role": "狼人"}, "身份"),
        ("day_started", {"round": 1}, "第 1 天"),
        (
            "werewolf_vote",
            {"player": "曹操", "target": "刘备", "kill_strategy": "威胁最大"},
            "狼人决策",
        ),
        ("seer_result", {"target": "曹操", "is_werewolf": True}, "狼人"),
        ("night_result", {"deaths": ["刘备"]}, "刘备"),
        ("night_result", {"deaths": []}, "平安夜"),
        ("hunter_action", {"player": "关羽", "target": None}, "不开枪"),
        (
            "vote_result",
            {"voted_out": "曹操", "votes": 4, "hunter_shot": "刘备"},
            "猎人带走 刘备",
        ),
        ("game_finished", {"winner": "villagers"}, "游戏结束"),
        ("game_cancelled", {}, "game_cancelled"),
    ],
)
def test_console_formats_supported_game_events(
    event_type: str,
    payload: dict[str, object],
    expected: str,
) -> None:
    rendered = format_event(event(event_type, payload))
    assert rendered is not None
    assert expected in rendered


def test_console_ignores_unknown_events() -> None:
    assert format_event(event("unknown", {})) is None
