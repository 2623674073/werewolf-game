from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel, Field, model_validator


def _candidate_names(candidates: Sequence[str]) -> tuple[str, ...]:
    names = tuple(name.strip() for name in candidates)
    if not names or any(not name for name in names):
        raise ValueError("候选玩家不能为空")
    if len(set(names)) != len(names):
        raise ValueError("候选玩家姓名必须唯一")
    return names


def vote_model(candidates: Sequence[str]) -> type[BaseModel]:
    names = _candidate_names(candidates)

    class Vote(BaseModel):
        vote: Literal[names]  # type: ignore[valid-type]
        reason: str
        suspicion_level: int = Field(ge=1, le=10)

    return Vote


def werewolf_kill_model(candidates: Sequence[str]) -> type[BaseModel]:
    names = _candidate_names(candidates)

    class WerewolfKill(BaseModel):
        target: Literal[names]  # type: ignore[valid-type]
        kill_strategy: str
        team_coordination: str | None = None

    return WerewolfKill


def seer_model(candidates: Sequence[str]) -> type[BaseModel]:
    names = _candidate_names(candidates)

    class SeerDecision(BaseModel):
        target: Literal[names]  # type: ignore[valid-type]
        check_reason: str
        priority_level: int = Field(ge=1, le=10)

    return SeerDecision


def hunter_model(candidates: Sequence[str]) -> type[BaseModel]:
    names = _candidate_names(candidates)

    class HunterDecision(BaseModel):
        shoot: bool
        target: Literal[names] | None = None  # type: ignore[valid-type]
        shoot_reason: str | None = None

        @model_validator(mode="after")
        def validate_target(self) -> HunterDecision:
            if self.shoot != (self.target is not None):
                raise ValueError("开枪选择与目标不一致")
            return self

    return HunterDecision


class WitchAction(BaseModel):
    action: Literal["不行动", "使用解药", "使用毒药"]
    target_name: str | None = None
    action_reason: str | None = None

    @model_validator(mode="after")
    def validate_target(self) -> WitchAction:
        if self.action == "不行动" and self.target_name is not None:
            raise ValueError("不行动时不能指定目标")
        if self.action != "不行动" and not self.target_name:
            raise ValueError("使用药品时必须指定目标")
        return self
