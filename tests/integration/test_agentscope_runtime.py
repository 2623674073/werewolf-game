from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from agentscope.event import TextBlockDeltaEvent
from agentscope.message import AssistantMsg
from agentscope.model import OpenAIChatModel
from pydantic import BaseModel

from werewolf_game.domain.models import GamePlayer, GameState
from werewolf_game.infrastructure.agentscope_runtime import (
    AgentScopeRuntime,
    build_openai_compatible_model,
)


class Choice(BaseModel):
    target: str


class FakeModel:
    async def generate_structured_output(
        self, messages: list[Any], structured_model: type[BaseModel]
    ) -> Any:
        assert any(message.get_text_content() == "私密选择" for message in messages)
        return SimpleNamespace(content={"target": "曹操"})


class FakeAgent:
    def __init__(self, name: str, system_prompt: str, model: FakeModel) -> None:
        self.name = name
        self.system_prompt = system_prompt
        self.model = model
        self.state = SimpleNamespace(context=[])
        self.observed: list[Any] = []

    async def observe(self, message: Any) -> None:
        messages = message if isinstance(message, list) else [message]
        self.observed.extend(messages)
        self.state.context.extend(messages)

    async def reply(self, message: Any) -> Any:
        self.state.context.append(message)
        reply = AssistantMsg(name=self.name, content=f"{self.name}发言")
        self.state.context.append(reply)
        return reply

    async def reply_stream(self, message: Any) -> Any:
        self.state.context.append(message)
        content = f"{self.name}发言"
        for delta in (self.name, "发言"):
            yield TextBlockDeltaEvent(
                reply_id=f"reply-{self.name}",
                block_id="text",
                delta=delta,
            )
        self.state.context.append(AssistantMsg(name=self.name, content=content))


class FailingReplyAgent(FakeAgent):
    async def reply_stream(self, message: Any) -> Any:
        raise RuntimeError("single player failed")
        yield


class UnsupportedStreamError(RuntimeError):
    status_code = 400


class UnsupportedStreamAgent(FakeAgent):
    async def reply_stream(self, message: Any) -> Any:
        raise UnsupportedStreamError("streaming is unsupported")
        yield


class PartialStreamAgent(FakeAgent):
    async def reply_stream(self, message: Any) -> Any:
        yield TextBlockDeltaEvent(reply_id="partial", block_id="text", delta="半句")
        raise RuntimeError("connection lost")


def test_openai_compatible_factory_uses_generic_credential_and_formatter() -> None:
    model = build_openai_compatible_model(
        api_key="secret-key",
        model_name="deepseek-v4-flash",
        base_url="http://model.example/v1",
        timeout_seconds=45,
        max_retries=2,
    )
    assert isinstance(model, OpenAIChatModel)
    assert model.model == "deepseek-v4-flash"
    assert model.credential.base_url == "http://model.example/v1"
    assert model.stream is False
    assert model.client_kwargs["timeout"] == 45

    streaming = build_openai_compatible_model(
        api_key="secret-key",
        model_name="deepseek-v4-flash",
        base_url="http://model.example/v1",
        timeout_seconds=45,
        max_retries=2,
        stream=True,
    )
    assert streaming.stream is True


async def test_runtime_broadcasts_speech_but_keeps_decision_private() -> None:
    model = FakeModel()
    runtime = AgentScopeRuntime(
        model=model,
        max_model_concurrency=2,
        timeout_seconds=1,
        max_retries=0,
        agent_factory=lambda name, prompt, shared_model: FakeAgent(
            name, prompt, shared_model
        ),
    )
    game = GameState(
        id="game-1",
        player_count=2,
        players=[
            GamePlayer("刘备", "刘备", "村民"),
            GamePlayer("曹操", "曹操", "狼人"),
        ],
    )
    await runtime.setup(game, {"刘备": "村民提示", "曹操": "狼人提示"})

    activities = [
        activity
        async for activity in runtime.discuss("game-1", ["刘备", "曹操"], "公开讨论", 1)
    ]
    before = len(runtime._sessions["game-1"]["曹操"].observed)
    result = await runtime.decide("game-1", "刘备", "私密选择", Choice)

    assert result == Choice(target="曹操")
    assert [activity.kind for activity in activities] == [
        "turn_started",
        "speech_delta",
        "speech_delta",
        "speech_completed",
        "turn_started",
        "speech_delta",
        "speech_delta",
        "speech_completed",
    ]
    assert len(runtime._sessions["game-1"]["曹操"].observed) == before
    assert any(
        getattr(message, "name", "") == "刘备"
        for message in runtime._sessions["game-1"]["曹操"].observed
    )


async def test_runtime_continues_discussion_when_one_player_fails() -> None:
    def factory(name: str, prompt: str, model: FakeModel) -> FakeAgent:
        agent_type = FailingReplyAgent if name == "刘备" else FakeAgent
        return agent_type(name, prompt, model)

    runtime = AgentScopeRuntime(
        model=FakeModel(),
        max_model_concurrency=2,
        timeout_seconds=1,
        max_retries=0,
        agent_factory=factory,
    )
    game = GameState(
        id="game-failure",
        player_count=2,
        players=[
            GamePlayer("刘备", "刘备", "村民"),
            GamePlayer("曹操", "曹操", "狼人"),
        ],
    )
    await runtime.setup(game, {"刘备": "村民提示", "曹操": "狼人提示"})

    activities = [
        activity
        async for activity in runtime.discuss(
            "game-failure", ["刘备", "曹操"], "公开讨论", 1
        )
    ]

    speakers = [
        activity.player
        for activity in activities
        if activity.kind == "speech_completed"
    ]
    assert speakers == ["曹操"]


async def test_runtime_falls_back_only_when_streaming_is_unsupported() -> None:
    runtime = AgentScopeRuntime(
        model=FakeModel(),
        decision_model=FakeModel(),
        max_model_concurrency=1,
        timeout_seconds=1,
        max_retries=0,
        agent_factory=lambda name, prompt, model: UnsupportedStreamAgent(
            name, prompt, model
        ),
    )
    game = GameState(
        id="fallback",
        player_count=1,
        players=[GamePlayer("刘备", "刘备", "村民")],
    )
    await runtime.setup(game, {"刘备": "提示"})

    activities = [
        activity async for activity in runtime.discuss("fallback", ["刘备"], "讨论", 1)
    ]

    assert runtime._stream_supported is False
    assert [activity.kind for activity in activities] == [
        "turn_started",
        "speech_completed",
    ]
    assert activities[-1].stream_trace == ()


async def test_runtime_does_not_regenerate_after_partial_stream_failure() -> None:
    runtime = AgentScopeRuntime(
        model=FakeModel(),
        max_model_concurrency=1,
        timeout_seconds=1,
        max_retries=0,
        agent_factory=lambda name, prompt, model: PartialStreamAgent(
            name, prompt, model
        ),
    )
    game = GameState(
        id="partial",
        player_count=1,
        players=[GamePlayer("刘备", "刘备", "村民")],
    )
    await runtime.setup(game, {"刘备": "提示"})

    activities = [
        activity async for activity in runtime.discuss("partial", ["刘备"], "讨论", 1)
    ]

    assert [activity.kind for activity in activities] == [
        "turn_started",
        "speech_delta",
        "speech_failed",
    ]
    assert activities[-1].content == "半句"
