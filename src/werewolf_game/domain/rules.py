from __future__ import annotations

import random
from collections import Counter
from collections.abc import Mapping, Sequence

from werewolf_game.domain.models import GamePlayer

ROLE_DATA: dict[str, dict[str, str]] = {
    "狼人": {"team": "werewolves", "ability": "夜晚击杀一名非狼人玩家"},
    "预言家": {"team": "villagers", "ability": "每晚查验一名玩家"},
    "女巫": {"team": "villagers", "ability": "拥有解药和毒药各一瓶"},
    "猎人": {"team": "villagers", "ability": "白天被投票淘汰时可以开枪"},
    "村民": {"team": "villagers", "ability": "通过发言和投票找出狼人"},
}

CHARACTER_TRAITS: dict[str, str] = {
    "刘备": "仁德宽厚，善于团结众人",
    "关羽": "忠义刚烈，言辞直接",
    "张飞": "豪爽直接，容易冲动",
    "诸葛亮": "分析透彻，言辞谨慎",
    "赵云": "忠勇双全，话语简洁",
    "曹操": "善于权谋，话语犀利",
    "司马懿": "深谋远虑，言辞含蓄",
    "周瑜": "才华横溢，分析精准",
    "孙权": "善于决断，话语果决",
}

CHARACTER_NAMES = (
    "刘备",
    "关羽",
    "张飞",
    "诸葛亮",
    "赵云",
    "曹操",
    "司马懿",
    "典韦",
    "许褚",
    "夏侯惇",
    "孙权",
    "周瑜",
    "陆逊",
    "甘宁",
    "太史慈",
    "吕布",
    "貂蝉",
    "董卓",
    "袁绍",
    "袁术",
)


def validate_player_count(player_count: int) -> None:
    if not 6 <= player_count <= 12:
        raise ValueError("游戏人数必须在 6 到 12 人之间")


def role_setup(player_count: int) -> list[str]:
    validate_player_count(player_count)
    if player_count == 6:
        return ["狼人", "狼人", "预言家", "女巫", "村民", "村民"]
    if player_count in {8, 9}:
        roles = ["狼人"] * 3 + ["预言家", "女巫", "猎人"]
        return roles + ["村民"] * (player_count - len(roles))
    werewolf_count = player_count // 3
    roles = ["狼人"] * werewolf_count + ["预言家", "女巫", "猎人"]
    return roles + ["村民"] * (player_count - len(roles))


def majority_vote(
    votes: Mapping[str, str | None],
    *,
    valid_targets: Sequence[str],
    rng: random.Random,
) -> tuple[str | None, int]:
    valid = set(valid_targets)
    counts = Counter(target for target in votes.values() if target in valid)
    if not counts:
        return None, 0
    top_count = max(counts.values())
    tied = sorted(name for name, count in counts.items() if count == top_count)
    return rng.choice(tied), top_count


def check_winner(players: Sequence[GamePlayer]) -> str | None:
    alive = [player for player in players if player.is_alive]
    wolves = sum(player.role == "狼人" for player in alive)
    villagers = len(alive) - wolves
    if wolves == 0:
        return "villagers"
    if wolves >= villagers:
        return "werewolves"
    return None


def role_prompt(role: str, character: str) -> str:
    team_goal = (
        "隐藏身份并与狼队友合作消灭好人"
        if role == "狼人"
        else "通过发言、技能和投票找出全部狼人"
    )
    trait = CHARACTER_TRAITS.get(character, "沉着谨慎")
    ability = ROLE_DATA[role]["ability"]
    return (
        f"你是{character}，本局身份是{role}。目标：{team_goal}。"
        f"能力：{ability}。人物性格：{trait}。"
        "只依据主持人和对话提供的信息判断，不得泄露不应公开的身份信息。"
    )
