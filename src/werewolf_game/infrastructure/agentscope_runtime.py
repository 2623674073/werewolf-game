from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Callable, Sequence
from typing import Any

from agentscope.agent import Agent
from agentscope.credential import OpenAICredential
from agentscope.formatter import OpenAIMultiAgentFormatter
from agentscope.message import AssistantMsg, SystemMsg, UserMsg
from agentscope.model import OpenAIChatModel
from pydantic import BaseModel, SecretStr

from werewolf_game.application.ports import DiscussionActivity
from werewolf_game.domain.models import GameState

AgentFactory = Callable[[str, str, Any], Any]
logger = logging.getLogger(__name__)


def build_openai_compatible_model(
    api_key: str,
    model_name: str,
    base_url: str,
    timeout_seconds: float,
    max_retries: int,
) -> OpenAIChatModel:
    return OpenAIChatModel(
        credential=OpenAICredential(
            api_key=SecretStr(api_key),
            base_url=base_url,
        ),
        model=model_name,
        parameters=OpenAIChatModel.Parameters(thinking_enable=False),
        stream=False,
        max_retries=max_retries,
        formatter=OpenAIMultiAgentFormatter(),
        client_kwargs={"timeout": timeout_seconds},
    )


class AgentScopeRuntime:
    def __init__(
        self,
        *,
        model: Any,
        max_model_concurrency: int,
        timeout_seconds: float,
        max_retries: int,
        agent_factory: AgentFactory | None = None,
    ) -> None:
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self._semaphore = asyncio.Semaphore(max_model_concurrency)
        self._agent_factory = agent_factory or self._create_agent
        self._sessions: dict[str, dict[str, Any]] = {}
        self._prompts: dict[str, dict[str, str]] = {}

    @staticmethod
    def _create_agent(name: str, prompt: str, model: Any) -> Agent:
        return Agent(name=name, system_prompt=prompt, model=model)

    async def setup(self, game: GameState, prompts: dict[str, str]) -> None:
        self._prompts[game.id] = prompts.copy()
        self._sessions[game.id] = {
            player.name: self._agent_factory(
                player.name, prompts[player.name], self.model
            )
            for player in game.players
        }
        for player in game.players:
            identity = UserMsg(
                name="游戏主持人",
                content=f"你的身份是{player.role}。此消息为私密信息。",
            )
            await self._sessions[game.id][player.name].observe(identity)

    async def discuss(
        self,
        game_id: str,
        players: Sequence[str],
        announcement: str,
        rounds: int,
    ) -> AsyncIterator[DiscussionActivity]:
        agents = self._selected(game_id, players)
        opening = UserMsg(name="游戏主持人", content=announcement)
        await asyncio.gather(
            *(agent.observe(opening) for agent in agents.values()),
            return_exceptions=True,
        )
        for discussion_round in range(1, rounds + 1):
            for name, agent in agents.items():
                yield DiscussionActivity(
                    kind="turn_started",
                    player=name,
                    discussion_round=discussion_round,
                )
                prompt = UserMsg(name="游戏主持人", content=f"{name}，请发言。")
                try:
                    reply = await self._with_retry(agent.reply, prompt)
                except Exception:
                    logger.warning(
                        "player discussion failed",
                        extra={"game_id": game_id, "event_type": "discussion_failed"},
                    )
                    continue
                yield DiscussionActivity(
                    kind="speech",
                    player=name,
                    discussion_round=discussion_round,
                    content=reply.get_text_content(),
                )
                await asyncio.gather(
                    *(
                        recipient.observe(reply)
                        for other, recipient in agents.items()
                        if other != name
                    ),
                    return_exceptions=True,
                )

    async def decide(
        self,
        game_id: str,
        player: str,
        prompt: str,
        schema: type[BaseModel],
    ) -> BaseModel | None:
        agent = self._sessions[game_id][player]
        prompt_message = UserMsg(name="游戏主持人", content=prompt)
        messages = [
            SystemMsg(name="system", content=self._prompts[game_id][player]),
            *list(agent.state.context),
            prompt_message,
        ]
        try:
            response = await self._with_retry(
                agent.model.generate_structured_output,
                messages,
                structured_model=schema,
            )
            result = schema.model_validate(response.content)
            private = AssistantMsg(
                name=player,
                content=result.model_dump_json(),
                metadata=result.model_dump(),
            )
            await agent.observe([prompt_message, private])
            return result
        except Exception:
            return None

    async def close(self, game_id: str) -> None:
        self._sessions.pop(game_id, None)
        self._prompts.pop(game_id, None)

    def _selected(self, game_id: str, players: Sequence[str]) -> dict[str, Any]:
        return {name: self._sessions[game_id][name] for name in players}

    async def _with_retry(
        self, operation: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> Any:
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                async with self._semaphore:
                    return await asyncio.wait_for(
                        operation(*args, **kwargs), timeout=self.timeout_seconds
                    )
            except Exception as exc:
                last_error = exc
                if attempt < self.max_retries:
                    await asyncio.sleep(0.25 * (2**attempt))
        assert last_error is not None
        raise last_error
