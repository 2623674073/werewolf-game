from __future__ import annotations

import random

import pytest
from pydantic import ValidationError

from werewolf_game.domain.models import GamePlayer, GameStatus, Phase, Visibility
from werewolf_game.domain.rules import (
    check_winner,
    majority_vote,
    role_prompt,
    role_setup,
    validate_player_count,
)
from werewolf_game.domain.schemas import (
    WitchAction,
    hunter_model,
    vote_model,
    werewolf_kill_model,
)


@pytest.mark.parametrize("count", range(6, 13))
def test_role_setup_supports_six_to_twelve_players(count: int) -> None:
    roles = role_setup(count)
    assert len(roles) == count
    expected_wolves = {6: 2, 7: 2, 8: 3, 9: 3, 10: 3, 11: 3, 12: 4}
    assert roles.count("狼人") == expected_wolves[count]


@pytest.mark.parametrize("count", [0, 5, 13])
def test_player_count_rejects_unsupported_values(count: int) -> None:
    with pytest.raises(ValueError, match="6 到 12"):
        validate_player_count(count)


def test_game_player_only_initializes_witch_resources_for_witch() -> None:
    witch = GamePlayer(name="貂蝉", character="貂蝉", role="女巫")
    villager = GamePlayer(name="刘备", character="刘备", role="村民")
    assert witch.has_antidote and witch.has_poison
    assert not villager.has_antidote and not villager.has_poison


def test_dynamic_models_reject_unknown_targets_and_bad_candidates() -> None:
    model = vote_model(["刘备", "曹操"])
    with pytest.raises(ValidationError):
        model(vote="孙权", reason="可疑", suspicion_level=8)
    with pytest.raises(ValueError, match="唯一"):
        werewolf_kill_model(["刘备", "刘备"])


def test_witch_action_has_no_contradictory_state() -> None:
    with pytest.raises(ValidationError):
        WitchAction(action="不行动", target_name="刘备")
    with pytest.raises(ValidationError):
        WitchAction(action="使用毒药", target_name=None)


def test_hunter_decision_requires_target_only_when_shooting() -> None:
    model = hunter_model(["曹操"])
    assert model(shoot=False).target is None
    with pytest.raises(ValidationError):
        model(shoot=True)
    with pytest.raises(ValidationError):
        model(shoot=False, target="曹操")


def test_role_prompt_contains_identity_and_character() -> None:
    prompt = role_prompt("狼人", "曹操")
    assert "狼人" in prompt
    assert "曹操" in prompt


def test_majority_vote_ignores_invalid_and_uses_injected_rng() -> None:
    result, count = majority_vote(
        {"甲": "刘备", "乙": "曹操", "丙": "非法", "丁": None},
        valid_targets=["刘备", "曹操"],
        rng=random.Random(0),
    )
    assert result == "曹操"
    assert count == 1


def test_winner_uses_live_player_state() -> None:
    players = [
        GamePlayer("狼", "狼", "狼人", is_alive=False),
        GamePlayer("民", "民", "村民"),
    ]
    assert check_winner(players) == "villagers"


def test_public_enums_are_stable() -> None:
    assert GameStatus.CREATED.value == "created"
    assert Phase.NIGHT.value == "night"
    assert Visibility.PRIVATE.value == "private"
