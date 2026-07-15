from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

GameStatusValue = Literal[
    "created",
    "running",
    "completed",
    "draw",
    "cancelled",
    "interrupted",
    "failed",
]
PhaseValue = Literal["setup", "night", "day", "finished"]
VisibilityValue = Literal["public", "private", "internal"]
EventType = Literal[
    "identity_assigned",
    "game_started",
    "night_started",
    "day_started",
    "discussion_started",
    "speaker_turn_started",
    "speech",
    "speech_moderated",
    "werewolf_vote",
    "seer_result",
    "witch_action",
    "day_vote",
    "hunter_action",
    "night_result",
    "vote_result",
    "roles_revealed",
    "game_finished",
    "game_cancelled",
    "game_interrupted",
    "game_failed",
]


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="allow")


class CreateGameRequest(BaseModel):
    player_count: int = Field(ge=6, le=12)


class PlayerResponse(BaseModel):
    name: str
    character: str
    is_alive: bool
    role: str | None = None
    has_antidote: bool | None = None
    has_poison: bool | None = None


class GameResponse(BaseModel):
    id: str
    player_count: int
    status: GameStatusValue
    phase: PhaseValue
    round_number: int
    players: list[PlayerResponse]
    winner: str | None
    error_code: str | None
    created_at: str
    started_at: str | None
    finished_at: str | None


class SessionResponse(BaseModel):
    authenticated: Literal[True] = True
    capabilities: list[Literal["control", "public_view", "god_view"]]


class IdentityPayload(ApiModel):
    player: str
    role: str


class GameStartedPayload(ApiModel):
    players: list[str]


class PhaseStartedPayload(ApiModel):
    round: int


class DiscussionStartedPayload(ApiModel):
    discussion_kind: str
    round: int
    participants: list[str]


class SpeakerPayload(ApiModel):
    player: str
    round: int
    discussion_round: int
    discussion_kind: str


class SpeechPayload(SpeakerPayload):
    content: str


class ModeratedSpeechPayload(ApiModel):
    player: str
    status: Literal["blocked", "unavailable"]
    categories: list[str]


class WerewolfVotePayload(ApiModel):
    player: str
    target: str
    kill_strategy: str
    team_coordination: str | None = None


class SeerResultPayload(ApiModel):
    target: str
    is_werewolf: bool


class WitchActionPayload(ApiModel):
    player: str
    action: str
    target_name: str | None = None
    action_reason: str | None = None


class DayVotePayload(ApiModel):
    player: str
    vote: str
    reason: str
    suspicion_level: int


class HunterActionPayload(ApiModel):
    player: str
    shoot: bool
    target: str | None = None
    shoot_reason: str | None = None


class NightResultPayload(ApiModel):
    deaths: list[str]


class VoteResultPayload(ApiModel):
    voted_out: str | None
    votes: int
    hunter_shot: str | None


class RevealedRole(BaseModel):
    player: str
    role: str


class RolesRevealedPayload(ApiModel):
    players: list[RevealedRole]


class FinishedPayload(ApiModel):
    winner: str


class ErrorPayload(ApiModel):
    error_code: str | None = None


EventPayload = (
    IdentityPayload
    | GameStartedPayload
    | PhaseStartedPayload
    | DiscussionStartedPayload
    | SpeakerPayload
    | SpeechPayload
    | ModeratedSpeechPayload
    | WerewolfVotePayload
    | SeerResultPayload
    | WitchActionPayload
    | DayVotePayload
    | HunterActionPayload
    | NightResultPayload
    | VoteResultPayload
    | RolesRevealedPayload
    | FinishedPayload
    | ErrorPayload
    | dict[str, Any]
)


class EventResponse(BaseModel):
    game_id: str
    seq: int
    type: EventType
    phase: PhaseValue
    visibility: VisibilityValue
    recipients: list[str]
    payload: EventPayload
    created_at: str


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str


class ErrorResponse(BaseModel):
    error: ErrorDetail
