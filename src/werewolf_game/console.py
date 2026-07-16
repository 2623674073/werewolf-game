from __future__ import annotations

from collections.abc import AsyncIterator, Callable

from werewolf_game.application.events import StreamEvent
from werewolf_game.domain.models import GameEvent, Visibility


def format_event(event: GameEvent) -> str | None:
    payload = event.payload
    if event.type == "game_started":
        return f"=== 游戏开始：{'、'.join(payload.get('players', []))} ==="
    if event.type == "identity_assigned":
        return f"[身份][私密] {payload.get('player')}：{payload.get('role')}"
    if event.type == "night_started":
        return f"\n=== 第 {payload.get('round')} 夜 ==="
    if event.type == "day_started":
        return f"\n=== 第 {payload.get('round')} 天 ==="
    if event.type == "speech":
        label = "私密发言" if event.visibility is Visibility.PRIVATE else "发言"
        return f"[{label}] {payload.get('player')}：{payload.get('content')}"
    if event.type == "werewolf_vote":
        return (
            f"[狼人决策][私密] {payload.get('player')} → {payload.get('target')}："
            f"{payload.get('kill_strategy', '')}"
        )
    if event.type == "seer_result":
        identity = "狼人" if payload.get("is_werewolf") else "好人"
        return f"[预言家][私密] 查验 {payload.get('target')}：{identity}"
    if event.type == "witch_action":
        return (
            f"[女巫][私密] {payload.get('player')}：{payload.get('action')} "
            f"{payload.get('target_name') or ''}"
        ).rstrip()
    if event.type == "night_result":
        deaths = payload.get("deaths") or []
        return f"[夜晚结果] {'、'.join(deaths) if deaths else '平安夜'}"
    if event.type == "day_vote":
        return (
            f"[投票][私密] {payload.get('player')} 投给{payload.get('vote')}："
            f"{payload.get('reason', '')}"
        )
    if event.type == "hunter_action":
        target = payload.get("target") or "不开枪"
        return f"[猎人][私密] {payload.get('player')}：{target}"
    if event.type == "vote_result":
        voted_out = payload.get("voted_out") or "无人"
        shot = payload.get("hunter_shot")
        suffix = f"；猎人带走 {shot}" if shot else ""
        return f"[投票结果] 淘汰 {voted_out}（{payload.get('votes', 0)} 票）{suffix}"
    if event.type == "game_finished":
        return f"\n=== 游戏结束：{payload.get('winner')} ==="
    if event.type in {"game_cancelled", "game_interrupted", "game_failed"}:
        return f"[系统] {event.type}"
    return None


class ConsolePresenter:
    def __init__(self, printer: Callable[[str], None] = print) -> None:
        self.printer = printer

    async def consume(self, events: AsyncIterator[StreamEvent]) -> None:
        async for event in events:
            if not isinstance(event, GameEvent):
                continue
            line = format_event(event)
            if line is not None:
                self.printer(line)
