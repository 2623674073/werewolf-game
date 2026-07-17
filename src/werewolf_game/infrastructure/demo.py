from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime
from typing import Any, get_args

from pydantic import BaseModel

from werewolf_game.application.ports import DiscussionActivity, SpeechTraceChunk
from werewolf_game.domain.models import GamePlayer, GameState
from werewolf_game.domain.reviews import (
    GameDossier,
    GameReviewResult,
    PlayerReview,
    TurningPoint,
)


class DemoAgentRuntime:
    """Deterministic offline runtime for evaluation and product demos."""

    def __init__(self, *, chunk_delay: float = 0.025) -> None:
        self.chunk_delay = chunk_delay
        self._games: dict[str, dict[str, GamePlayer]] = {}

    async def setup(self, game: GameState, prompts: dict[str, str]) -> None:
        del prompts
        self._games[game.id] = {player.name: player for player in game.players}

    async def discuss(
        self,
        game_id: str,
        players: Sequence[str],
        announcement: str,
        rounds: int,
    ) -> AsyncIterator[DiscussionActivity]:
        del announcement
        roster = self._games[game_id]
        for discussion_round in range(1, rounds + 1):
            for name in players:
                yield DiscussionActivity("turn_started", name, discussion_round)
                player = roster[name]
                text = self._speech(player, roster.values())
                content = ""
                trace: list[SpeechTraceChunk] = []
                started_at = datetime.now(UTC)
                for index, delta in enumerate(_chunks(text), start=1):
                    await asyncio.sleep(self.chunk_delay)
                    content += delta
                    offset_ms = round(index * self.chunk_delay * 1000)
                    trace.append(SpeechTraceChunk(offset_ms, delta))
                    yield DiscussionActivity(
                        "speech_delta",
                        name,
                        discussion_round,
                        content=content,
                        delta=delta,
                        offset_ms=offset_ms,
                        stream_started_at=started_at,
                    )
                yield DiscussionActivity(
                    "speech_completed",
                    name,
                    discussion_round,
                    content=content,
                    stream_started_at=started_at,
                    stream_trace=tuple(trace),
                )

    async def decide(
        self,
        game_id: str,
        player: str,
        prompt: str,
        schema: type[BaseModel],
    ) -> BaseModel | None:
        del prompt
        roster = self._games[game_id]
        fields = schema.model_fields
        if "action" in fields:
            return schema.model_validate(
                {"action": "不行动", "target_name": None, "action_reason": "保留药品"}
            )
        if "shoot" in fields:
            return schema.model_validate(
                {"shoot": False, "target": None, "shoot_reason": "证据不足"}
            )
        if "vote" in fields:
            target = self._target(schema, "vote", roster, player, prefer_wolf=True)
            return schema.model_validate(
                {
                    "vote": target,
                    "reason": "离线演示采用确定性证据链",
                    "suspicion_level": 8,
                }
            )
        if "kill_strategy" in fields:
            target = self._target(schema, "target", roster, player, prefer_wolf=False)
            return schema.model_validate(
                {
                    "target": target,
                    "kill_strategy": "优先削弱好人阵营",
                    "team_coordination": "按固定演示策略执行",
                }
            )
        if "check_reason" in fields:
            target = self._target(schema, "target", roster, player, prefer_wolf=True)
            return schema.model_validate(
                {
                    "target": target,
                    "check_reason": "优先查验高风险目标",
                    "priority_level": 8,
                }
            )
        return None

    async def close(self, game_id: str) -> None:
        self._games.pop(game_id, None)

    async def shutdown(self) -> None:
        self._games.clear()

    @staticmethod
    def _target(
        schema: type[BaseModel],
        field: str,
        roster: dict[str, GamePlayer],
        actor: str,
        *,
        prefer_wolf: bool,
    ) -> str:
        annotation = schema.model_fields[field].annotation
        candidates = [value for value in get_args(annotation) if isinstance(value, str)]
        if not candidates:
            raw = schema.model_json_schema()["properties"][field]
            candidates = list(raw.get("enum", []))
        actor_is_wolf = roster[actor].role == "狼人"
        desired_wolf = prefer_wolf and not actor_is_wolf
        return next(
            (
                name
                for name in candidates
                if name in roster and (roster[name].role == "狼人") is desired_wolf
            ),
            candidates[0],
        )

    @staticmethod
    def _speech(player: GamePlayer, players: Any) -> str:
        alive = [candidate.name for candidate in players if candidate.is_alive]
        if player.role == "狼人":
            return (
                f"{player.name}环顾众人：线索尚乱，先从发言次序与投票变化中寻找破绽。"
            )
        wolves = [candidate.name for candidate in players if candidate.role == "狼人"]
        suspect = next((name for name in wolves if name in alive), alive[0])
        return (
            f"{player.name}沉吟道：我会重点审视{suspect}的立场，"
            "诸位也请给出可验证的理由。"
        )


class DemoGameHistorian:
    async def generate_review(self, dossier: GameDossier) -> GameReviewResult:
        seqs = [event.seq for event in dossier.events]
        first = seqs[0]
        last = seqs[-1]
        mvp = next(
            (player.name for player in dossier.players if player.is_alive),
            dossier.players[0].name,
        )
        return GameReviewResult(
            title="群雄夜宴·离线推演录",
            overview=(
                f"本局经过 {dossier.total_rounds} 回合，"
                f"以 {dossier.winner} 阵营结果收束。"
            ),
            turning_points=[
                TurningPoint(
                    title="身份落定",
                    analysis="各阵营进入推演。",
                    event_seqs=[first],
                ),
                TurningPoint(
                    title="终局裁定",
                    analysis="关键投票决定最终走势。",
                    event_seqs=[last],
                ),
            ],
            winning_factors=["阵营目标明确", "关键投票形成多数"],
            player_reviews=[
                PlayerReview(
                    player=item.name,
                    character=item.character,
                    role=item.role,
                    score=8.0 if item.name == mvp else 7.0,
                    role_completion="完成了离线演示中的阵营行动。",
                    highlights=["保持了稳定的决策链"],
                    mistakes=[],
                    evidence_event_seqs=[first],
                )
                for item in dossier.players
            ],
            mvp=mvp,
            closing_comment="此卷为确定性离线演示，用于验证完整产品流程，不代表真实模型能力。",
        )

    async def close(self) -> None:
        return None


def _chunks(text: str, size: int = 8) -> list[str]:
    return [text[index : index + size] for index in range(0, len(text), size)]
