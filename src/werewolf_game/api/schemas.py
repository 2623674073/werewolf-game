from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel

from werewolf_game.domain.reviews import GameReviewResult

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
    persona_tags: list[str] = Field(default_factory=list)


class GameResponse(BaseModel):
    id: str
    player_count: int
    status: GameStatusValue
    phase: PhaseValue
    round_number: int
    players: list[PlayerResponse]
    winner: str | None = None
    error_code: str | None = None
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None


class SessionResponse(BaseModel):
    authenticated: Literal[True] = True
    capabilities: list[Literal["control", "public_view", "god_view"]]
    runtime_mode: Literal["openai", "demo"]
    version: str


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
    stream_started_at: str | None = None
    stream_trace: list[SpeechTraceChunkResponse] = Field(default_factory=list)


class SpeechTraceChunkResponse(BaseModel):
    offset_ms: int = Field(ge=0)
    delta: str


class SpeechDeltaPayload(SpeakerPayload):
    content_so_far: str
    delta: str
    offset_ms: int = Field(ge=0)


class SpeechFailedPayload(SpeakerPayload):
    content_so_far: str = ""


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


class EventEnvelope(BaseModel):
    game_id: str
    seq: int
    phase: PhaseValue
    visibility: VisibilityValue
    recipients: list[str]
    created_at: str


class IdentityAssignedEvent(EventEnvelope):
    type: Literal["identity_assigned"]
    payload: IdentityPayload


class GameStartedEvent(EventEnvelope):
    type: Literal["game_started"]
    payload: GameStartedPayload


class PhaseStartedEvent(EventEnvelope):
    type: Literal["night_started", "day_started"]
    payload: PhaseStartedPayload


class DiscussionStartedEvent(EventEnvelope):
    type: Literal["discussion_started"]
    payload: DiscussionStartedPayload


class SpeakerTurnStartedEvent(EventEnvelope):
    type: Literal["speaker_turn_started"]
    payload: SpeakerPayload


class SpeechEvent(EventEnvelope):
    type: Literal["speech"]
    payload: SpeechPayload


class LegacyModeratedSpeechEvent(EventEnvelope):
    type: Literal["speech_moderated"]
    payload: ModeratedSpeechPayload


class WerewolfVoteEvent(EventEnvelope):
    type: Literal["werewolf_vote"]
    payload: WerewolfVotePayload


class SeerResultEvent(EventEnvelope):
    type: Literal["seer_result"]
    payload: SeerResultPayload


class WitchActionEvent(EventEnvelope):
    type: Literal["witch_action"]
    payload: WitchActionPayload


class DayVoteEvent(EventEnvelope):
    type: Literal["day_vote"]
    payload: DayVotePayload


class HunterActionEvent(EventEnvelope):
    type: Literal["hunter_action"]
    payload: HunterActionPayload


class NightResultEvent(EventEnvelope):
    type: Literal["night_result"]
    payload: NightResultPayload


class VoteResultEvent(EventEnvelope):
    type: Literal["vote_result"]
    payload: VoteResultPayload


class RolesRevealedEvent(EventEnvelope):
    type: Literal["roles_revealed"]
    payload: RolesRevealedPayload


class GameFinishedEvent(EventEnvelope):
    type: Literal["game_finished"]
    payload: FinishedPayload


class TerminalErrorEvent(EventEnvelope):
    type: Literal["game_cancelled", "game_interrupted", "game_failed"]
    payload: ErrorPayload


PersistedEvent = Annotated[
    IdentityAssignedEvent
    | GameStartedEvent
    | PhaseStartedEvent
    | DiscussionStartedEvent
    | SpeakerTurnStartedEvent
    | SpeechEvent
    | LegacyModeratedSpeechEvent
    | WerewolfVoteEvent
    | SeerResultEvent
    | WitchActionEvent
    | DayVoteEvent
    | HunterActionEvent
    | NightResultEvent
    | VoteResultEvent
    | RolesRevealedEvent
    | GameFinishedEvent
    | TerminalErrorEvent,
    Field(discriminator="type"),
]


class EventResponse(RootModel[PersistedEvent]):
    pass


class StreamEnvelope(BaseModel):
    game_id: str
    phase: PhaseValue
    visibility: VisibilityValue
    recipients: list[str]
    created_at: str


class SpeechDeltaFrame(StreamEnvelope):
    type: Literal["speech_delta"]
    payload: SpeechDeltaPayload


class SpeechFailedFrame(StreamEnvelope):
    type: Literal["speech_failed"]
    payload: SpeechFailedPayload


TransientSpeechFrame = Annotated[
    SpeechDeltaFrame | SpeechFailedFrame,
    Field(discriminator="type"),
]


class SpeechStreamFrameResponse(RootModel[TransientSpeechFrame]):
    pass


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


class GameReviewResponse(BaseModel):
    game_id: str
    status: Literal["pending", "completed", "failed"]
    result: GameReviewResult | None = None
    error_code: str | None = None
    created_at: str
    completed_at: str | None = None
