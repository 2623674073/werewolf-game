from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from werewolf_game.application.ports import GameHistorian
from werewolf_game.config import Settings
from werewolf_game.domain.reviews import GameDossier, GameReviewResult
from werewolf_game.infrastructure.agentscope_runtime import (
    build_openai_compatible_model,
)
from werewolf_game.infrastructure.historian import ModelGameHistorian


def create_historian_server(historian: GameHistorian) -> FastMCP:
    server = FastMCP(
        "Werewolf Game Historian",
        instructions=(
            "Generate a structured, evidence-based post-game review from a "
            "completed werewolf-game dossier."
        ),
    )

    @server.tool()
    async def generate_game_review(dossier: GameDossier) -> GameReviewResult:
        """Analyze one completed game dossier from an omniscient perspective."""
        return await historian.generate_review(dossier)

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
    return create_historian_server(
        ModelGameHistorian(model, timeout_seconds=settings.llm_timeout)
    )


def main() -> None:
    build_server().run(transport="stdio")


if __name__ == "__main__":
    main()
