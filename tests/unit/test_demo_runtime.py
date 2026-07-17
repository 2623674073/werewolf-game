from __future__ import annotations

from werewolf_game.domain.models import GamePlayer, GameState
from werewolf_game.domain.reviews import (
    DossierEvent,
    DossierPlayer,
    GameDossier,
)
from werewolf_game.domain.schemas import (
    WitchAction,
    hunter_model,
    seer_model,
    vote_model,
    werewolf_kill_model,
)
from werewolf_game.infrastructure.demo import DemoAgentRuntime, DemoGameHistorian


async def test_demo_runtime_streams_and_makes_deterministic_decisions() -> None:
    runtime = DemoAgentRuntime(chunk_delay=0)
    game = GameState(id="demo", player_count=3)
    game.players = [
        GamePlayer("曹操", "曹操", "狼人"),
        GamePlayer("刘备", "刘备", "预言家"),
        GamePlayer("关羽", "关羽", "猎人"),
    ]
    await runtime.setup(game, {player.name: "prompt" for player in game.players})

    activities = [
        item
        async for item in runtime.discuss(
            game.id,
            ["曹操", "刘备"],
            "公开讨论",
            1,
        )
    ]
    assert [item.kind for item in activities].count("speech_completed") == 2
    assert any(item.kind == "speech_delta" for item in activities)
    assert "曹操" in next(
        item.content or ""
        for item in activities
        if item.player == "刘备" and item.kind == "speech_completed"
    )

    wolf = await runtime.decide(
        game.id,
        "曹操",
        "kill",
        werewolf_kill_model(["刘备", "关羽"]),
    )
    seer = await runtime.decide(
        game.id,
        "刘备",
        "check",
        seer_model(["曹操", "关羽"]),
    )
    vote = await runtime.decide(
        game.id,
        "刘备",
        "vote",
        vote_model(["曹操", "关羽"]),
    )
    witch = await runtime.decide(game.id, "刘备", "witch", WitchAction)
    hunter = await runtime.decide(
        game.id,
        "关羽",
        "hunter",
        hunter_model(["曹操", "刘备"]),
    )
    assert wolf is not None and wolf.model_dump()["target"] == "刘备"
    assert seer is not None and seer.model_dump()["target"] == "曹操"
    assert vote is not None and vote.model_dump()["vote"] == "曹操"
    assert witch is not None and witch.model_dump()["action"] == "不行动"
    assert hunter is not None and hunter.model_dump()["shoot"] is False
    await runtime.close(game.id)


async def test_demo_historian_returns_evidence_based_full_roster() -> None:
    dossier = GameDossier(
        game_id="demo",
        winner="villagers",
        total_rounds=1,
        players=[
            DossierPlayer(name="刘备", character="刘备", role="村民", is_alive=True),
            DossierPlayer(name="曹操", character="曹操", role="狼人", is_alive=False),
        ],
        events=[
            DossierEvent(
                seq=1,
                phase="setup",
                type="game_started",
                visibility="public",
            ),
            DossierEvent(
                seq=2,
                phase="finished",
                type="game_finished",
                visibility="public",
            ),
        ],
    )
    historian = DemoGameHistorian()
    result = await historian.generate_review(dossier)
    assert result.mvp == "刘备"
    assert {item.player for item in result.player_reviews} == {"刘备", "曹操"}
    assert {seq for point in result.turning_points for seq in point.event_seqs} <= {
        1,
        2,
    }
    await historian.close()
