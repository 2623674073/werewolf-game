from __future__ import annotations

from typing import Literal

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from werewolf_game.application.moderation import (
    ModerationCategory,
    ModerationStatus,
)
from werewolf_game.application.ports import SpeechModerator
from werewolf_game.config import Settings
from werewolf_game.infrastructure.agentscope_runtime import (
    build_openai_compatible_model,
)
from werewolf_game.infrastructure.moderation import ModelSpeechModerator


class ModerationToolResult(BaseModel):
    status: Literal["allowed", "blocked"]
    categories: list[ModerationCategory] = Field(default_factory=list)
    reason: str = Field(default="", max_length=200)


def create_moderation_server(moderator: SpeechModerator) -> FastMCP:
    server = FastMCP(
        "Werewolf Speech Moderation",
        instructions=(
            "Review public werewolf-game speeches before they are persisted. "
            "Game-mechanic violence is fictional and allowed."
        ),
    )

    @server.tool()
    async def review_speech(
        player: str,
        phase: str,
        round_number: int,
        content: str,
    ) -> ModerationToolResult:
        """Classify one public player speech using the game moderation policy."""
        decision = await moderator.review_speech(
            player=player,
            phase=phase,
            round_number=round_number,
            content=content,
        )
        if decision.status is ModerationStatus.UNAVAILABLE:
            raise RuntimeError("moderation service is unavailable")
        return ModerationToolResult.model_validate(decision.model_dump())

    return server


def build_server(settings: Settings | None = None) -> FastMCP:
    settings = settings or Settings()  # type: ignore[call-arg]
    model = build_openai_compatible_model(
        api_key=settings.llm_api_key.get_secret_value(),
        model_name=settings.llm_model_id,
        base_url=settings.llm_base_url,
        timeout_seconds=settings.llm_timeout,
        max_retries=settings.model_max_retries,
    )
    return create_moderation_server(
        ModelSpeechModerator(model, timeout_seconds=settings.llm_timeout)
    )


def main() -> None:
    build_server().run(transport="stdio")


if __name__ == "__main__":
    main()
