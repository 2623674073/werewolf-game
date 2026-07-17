from __future__ import annotations

import json
import logging
from pathlib import Path

from werewolf_game.api.app import build_components, create_app
from werewolf_game.config import Settings


def main() -> None:
    logging.getLogger("werewolf_game.api.app").setLevel(logging.CRITICAL)
    target = Path(__file__).resolve().parents[1] / "frontend" / "openapi.json"
    settings = Settings(
        llm_api_key="schema-only-key",
        llm_model_id="schema-only-model",
        llm_base_url="http://schema.invalid/v1",
        app_api_token="schema-only-token-24-characters",
        database_url="sqlite+aiosqlite:///:memory:",
    )
    target.write_text(
        json.dumps(
            create_app(build_components(settings)).openapi(),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
