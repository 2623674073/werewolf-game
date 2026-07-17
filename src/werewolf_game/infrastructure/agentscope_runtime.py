from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Callable, Sequence
from datetime import UTC, datetime
from time import monotonic
from typing import Any

from agentscope.agent import Agent
from agentscope.credential import OpenAICredential
from agentscope.event import TextBlockDeltaEvent
from agentscope.formatter import OpenAIMultiAgentFormatter
from agentscope.message import AssistantMsg, SystemMsg, UserMsg
from agentscope.model import OpenAIChatModel
from httpx import AsyncClient
from pydantic import BaseModel, SecretStr

from werewolf_game.application.metrics import ApplicationMetrics, NullMetrics
from werewolf_game.application.ports import DiscussionActivity, SpeechTraceChunk
from werewolf_game.domain.models import GameState

AgentFactory = Callable[[str, str, Any], Any]
logger = logging.getLogger(__name__)


def build_openai_compatible_model(
    api_key: str,
    model_name: str,
    base_url: str,
    timeout_seconds: float,
    max_retries: int,
    *,
    stream: bool = False,
    trust_env: bool = False,
) -> OpenAIChatModel:
    return OpenAIChatModel(
        credential=OpenAICredential(
            api_key=SecretStr(api_key),
            base_url=base_url,
        ),
        model=model_name,
        parameters=OpenAIChatModel.Parameters(thinking_enable=False),
        stream=stream,
        max_retries=max_retries,
        formatter=OpenAIMultiAgentFormatter(),
        client_kwargs={
            "timeout": timeout_seconds,
            "http_client": AsyncClient(
                timeout=timeout_seconds,
                trust_env=trust_env,
            ),
        },
    )


class AgentScopeRuntime:
    def __init__(
        self,
        *,
        model: Any,
        decision_model: Any | None = None,
        max_model_concurrency: int,
        timeout_seconds: float,
        max_retries: int,
        agent_factory: AgentFactory | None = None,
        metrics: ApplicationMetrics | None = None,
    ) -> None:
        self.model = model
        self.decision_model = decision_model or model
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self._semaphore = asyncio.Semaphore(max_model_concurrency)
        self._agent_factory = agent_factory or self._create_agent
        self.metrics = metrics or NullMetrics()
        self._sessions: dict[str, dict[str, Any]] = {}
        self._prompts: dict[str, dict[str, str]] = {}
        self._stream_supported: bool | None = None

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
                if self._stream_supported is False:
                    reply = await self._fallback_reply(agent, prompt)
                    if reply is None:
                        yield DiscussionActivity(
                            kind="speech_failed",
                            player=name,
                            discussion_round=discussion_round,
                        )
                        continue
                    content = reply.get_text_content()
                    yield DiscussionActivity(
                        kind="speech_completed",
                        player=name,
                        discussion_round=discussion_round,
                        content=content,
                    )
                    await self._broadcast_reply(agents, name, reply)
                    continue

                content = ""
                trace: list[SpeechTraceChunk] = []
                started_at: datetime | None = None
                started_clock: float | None = None
                try:
                    call_started = monotonic()
                    async with self._semaphore:
                        async with asyncio.timeout(self.timeout_seconds):
                            async for event in agent.reply_stream(prompt):
                                if not isinstance(event, TextBlockDeltaEvent):
                                    continue
                                if not event.delta:
                                    continue
                                if started_at is None:
                                    started_at = datetime.now(UTC)
                                    started_clock = monotonic()
                                content += event.delta
                                offset_ms = round(
                                    (monotonic() - (started_clock or monotonic()))
                                    * 1000
                                )
                                if trace and offset_ms - trace[-1].offset_ms < 40:
                                    previous = trace[-1]
                                    trace[-1] = SpeechTraceChunk(
                                        offset_ms=offset_ms,
                                        delta=previous.delta + event.delta,
                                    )
                                else:
                                    trace.append(
                                        SpeechTraceChunk(
                                            offset_ms=offset_ms,
                                            delta=event.delta,
                                        )
                                    )
                                yield DiscussionActivity(
                                    kind="speech_delta",
                                    player=name,
                                    discussion_round=discussion_round,
                                    content=content,
                                    delta=event.delta,
                                    offset_ms=offset_ms,
                                    stream_started_at=started_at,
                                )
                    self._stream_supported = True
                    self.metrics.model_call(
                        "discussion_stream", "success", monotonic() - call_started
                    )
                except Exception as exc:
                    self.metrics.model_call(
                        "discussion_stream", "error", monotonic() - call_started
                    )
                    if not content and self._is_stream_unsupported(exc):
                        self._stream_supported = False
                        self.metrics.model_call("discussion_fallback", "used", 0)
                        reply = await self._fallback_reply(agent, prompt)
                        if reply is not None:
                            content = reply.get_text_content()
                            yield DiscussionActivity(
                                kind="speech_completed",
                                player=name,
                                discussion_round=discussion_round,
                                content=content,
                            )
                            await self._broadcast_reply(agents, name, reply)
                            continue
                    logger.warning(
                        "player discussion failed",
                        extra={"game_id": game_id, "event_type": "discussion_failed"},
                    )
                    yield DiscussionActivity(
                        kind="speech_failed",
                        player=name,
                        discussion_round=discussion_round,
                        content=content,
                    )
                    continue
                if not content:
                    yield DiscussionActivity(
                        kind="speech_failed",
                        player=name,
                        discussion_round=discussion_round,
                    )
                    continue
                reply = AssistantMsg(name=name, content=content)
                yield DiscussionActivity(
                    kind="speech_completed",
                    player=name,
                    discussion_round=discussion_round,
                    content=content,
                    stream_started_at=started_at,
                    stream_trace=tuple(trace),
                )
                await self._broadcast_reply(agents, name, reply)

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
            call_started = monotonic()
            response = await self._with_retry(
                self.decision_model.generate_structured_output,
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
            self.metrics.model_call(
                "structured_decision", "success", monotonic() - call_started
            )
            return result
        except Exception:
            self.metrics.model_call(
                "structured_decision", "error", monotonic() - call_started
            )
            return None

    async def close(self, game_id: str) -> None:
        self._sessions.pop(game_id, None)
        self._prompts.pop(game_id, None)

    async def shutdown(self) -> None:
        clients: dict[int, AsyncClient] = {}
        for model in (self.model, self.decision_model):
            client = getattr(model, "client_kwargs", {}).get("http_client")
            if isinstance(client, AsyncClient):
                clients[id(client)] = client
        await asyncio.gather(*(client.aclose() for client in clients.values()))
        self._sessions.clear()
        self._prompts.clear()

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
                    self.metrics.model_retry(
                        getattr(operation, "__name__", "model_operation")
                    )
                    await asyncio.sleep(0.25 * (2**attempt))
        assert last_error is not None
        raise last_error

    async def _fallback_reply(self, agent: Any, prompt: Any) -> Any | None:
        original_model = agent.model
        agent.model = self.decision_model
        try:
            return await self._with_retry(agent.reply, prompt)
        except Exception:
            return None
        finally:
            agent.model = original_model

    @staticmethod
    async def _broadcast_reply(
        agents: dict[str, Any], speaker: str, reply: Any
    ) -> None:
        await asyncio.gather(
            *(
                recipient.observe(reply)
                for other, recipient in agents.items()
                if other != speaker
            ),
            return_exceptions=True,
        )

    @staticmethod
    def _is_stream_unsupported(exc: Exception) -> bool:
        message = str(exc).lower()
        status_code = getattr(exc, "status_code", None)
        return status_code in {400, 404, 405, 422} and any(
            marker in message
            for marker in ("stream", "streaming", "unsupported", "not support")
        )
