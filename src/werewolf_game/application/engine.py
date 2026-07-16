from __future__ import annotations

import asyncio
import logging
import random
from datetime import UTC, datetime

from werewolf_game.application.events import EventCoordinator
from werewolf_game.application.ports import (
    AgentRuntime,
    GameRepository,
)
from werewolf_game.domain.models import (
    GamePlayer,
    GameState,
    GameStatus,
    Phase,
    Visibility,
)
from werewolf_game.domain.personas import character_profile
from werewolf_game.domain.rules import (
    CHARACTER_NAMES,
    check_winner,
    majority_vote,
    role_prompt,
    role_setup,
)
from werewolf_game.domain.schemas import (
    WitchAction,
    hunter_model,
    seer_model,
    vote_model,
    werewolf_kill_model,
)

logger = logging.getLogger(__name__)


class GameEngine:
    def __init__(
        self,
        runtime: AgentRuntime,
        repository: GameRepository,
        events: EventCoordinator,
        *,
        rng: random.Random | None = None,
        max_rounds: int = 10,
        discussion_rounds: int = 3,
    ) -> None:
        self.runtime = runtime
        self.repository = repository
        self.events = events
        self.rng = rng or random.Random()
        self.max_rounds = max_rounds
        self.discussion_rounds = discussion_rounds

    async def run(self, game: GameState) -> None:
        try:
            await self._setup(game)
            for round_number in range(1, self.max_rounds + 1):
                game.round_number = round_number
                await self._night(game)
                if await self._finish_if_won(game):
                    return
                await self._day(game)
                if await self._finish_if_won(game):
                    return
            await self._finish(game, GameStatus.DRAW, "draw")
        except asyncio.CancelledError:
            raise
        except Exception:
            game.status = GameStatus.FAILED
            game.phase = Phase.FINISHED
            game.error_code = "game_execution_failed"
            game.finished_at = datetime.now(UTC)
            await self.repository.save_game(game)
            await self.events.emit(
                game,
                "game_failed",
                {"error_code": game.error_code},
                visibility=Visibility.INTERNAL,
            )
            await self.events.broker.close_game(game.id)
        finally:
            await self.runtime.close(game.id)

    async def _setup(self, game: GameState) -> None:
        if not game.players:
            characters = self.rng.sample(list(CHARACTER_NAMES), game.player_count)
            roles = role_setup(game.player_count)
            game.players = [
                GamePlayer(
                    name=name,
                    character=name,
                    role=role,
                    persona_tags=list(character_profile(name).persona_tags),
                )
                for name, role in zip(characters, roles, strict=True)
            ]
        game.status = GameStatus.RUNNING
        game.phase = Phase.SETUP
        game.started_at = game.started_at or datetime.now(UTC)
        await self.repository.save_game(game)
        prompts = {
            player.name: role_prompt(player.role, player.character)
            for player in game.players
        }
        await self.runtime.setup(game, prompts)
        for player in game.players:
            await self.events.emit(
                game,
                "identity_assigned",
                {"player": player.name, "role": player.role},
                visibility=Visibility.PRIVATE,
                recipients=[player.name],
            )
        await self.events.emit(
            game,
            "game_started",
            {"players": [player.name for player in game.players]},
        )

    async def _night(self, game: GameState) -> None:
        game.phase = Phase.NIGHT
        await self.repository.save_game(game)
        alive = [player for player in game.players if player.is_alive]
        wolves = [player for player in alive if player.role == "狼人"]
        targets = [player for player in alive if player.role != "狼人"]
        await self.events.emit(game, "night_started", {"round": game.round_number})

        killed: str | None = None
        if wolves and targets:
            await self._discuss(
                game,
                wolves,
                "狼人讨论今晚的击杀目标",
                discussion_kind="werewolf",
                rounds=self.discussion_rounds,
                visibility=Visibility.PRIVATE,
                recipients=[player.name for player in wolves],
            )
            schema = werewolf_kill_model([player.name for player in targets])
            decisions = await asyncio.gather(
                *(
                    self.runtime.decide(game.id, wolf.name, "请选择击杀目标", schema)
                    for wolf in wolves
                )
            )
            for wolf, decision in zip(wolves, decisions, strict=True):
                if decision is not None:
                    await self.events.emit(
                        game,
                        "werewolf_vote",
                        {"player": wolf.name, **decision.model_dump()},
                        visibility=Visibility.PRIVATE,
                        recipients=[player.name for player in wolves],
                    )
            votes = {
                wolf.name: getattr(decision, "target", None)
                for wolf, decision in zip(wolves, decisions, strict=True)
            }
            killed, _ = majority_vote(
                votes,
                valid_targets=[player.name for player in targets],
                rng=self.rng,
            )
            killed = killed or self.rng.choice(targets).name

        seer = next((player for player in alive if player.role == "预言家"), None)
        if seer is not None:
            candidates = [player for player in alive if player.name != seer.name]
            decision = await self.runtime.decide(
                game.id,
                seer.name,
                "请选择查验目标",
                seer_model([player.name for player in candidates]),
            )
            target_name = getattr(decision, "target", None)
            target = next(
                (player for player in candidates if player.name == target_name), None
            )
            if target is not None:
                await self.events.emit(
                    game,
                    "seer_result",
                    {"target": target.name, "is_werewolf": target.role == "狼人"},
                    visibility=Visibility.PRIVATE,
                    recipients=[seer.name],
                )

        poisoned: str | None = None
        witch = next((player for player in alive if player.role == "女巫"), None)
        if witch is not None:
            action = await self.runtime.decide(
                game.id,
                witch.name,
                f"狼刀目标：{killed or '无'}，请选择女巫行动",
                WitchAction,
            )
            if action is not None:
                await self.events.emit(
                    game,
                    "witch_action",
                    {"player": witch.name, **action.model_dump()},
                    visibility=Visibility.PRIVATE,
                    recipients=[witch.name],
                )
            if (
                getattr(action, "action", None) == "使用解药"
                and witch.has_antidote
                and getattr(action, "target_name", None) == killed
            ):
                witch.has_antidote = False
                killed = None
            elif getattr(action, "action", None) == "使用毒药" and witch.has_poison:
                poison_target = getattr(action, "target_name", None)
                legal = {
                    player.name
                    for player in alive
                    if player.name not in {witch.name, killed}
                }
                if poison_target in legal:
                    witch.has_poison = False
                    poisoned = poison_target

        deaths = {name for name in (killed, poisoned) if name}
        for player in game.players:
            if player.name in deaths:
                player.eliminate()
        await self.repository.save_game(game)
        await self.events.emit(game, "night_result", {"deaths": sorted(deaths)})

    async def _day(self, game: GameState) -> None:
        game.phase = Phase.DAY
        await self.repository.save_game(game)
        alive = [player for player in game.players if player.is_alive]
        await self.events.emit(game, "day_started", {"round": game.round_number})
        await self._discuss(
            game,
            alive,
            "请根据已有信息依次发言",
            discussion_kind="day",
            rounds=1,
        )

        decisions = await asyncio.gather(
            *(
                self.runtime.decide(
                    game.id,
                    player.name,
                    "请选择要淘汰的玩家",
                    vote_model(
                        [
                            candidate.name
                            for candidate in alive
                            if candidate.name != player.name
                        ]
                    ),
                )
                for player in alive
            )
        )
        for player, decision in zip(alive, decisions, strict=True):
            if decision is not None:
                await self.events.emit(
                    game,
                    "day_vote",
                    {"player": player.name, **decision.model_dump()},
                    visibility=Visibility.PRIVATE,
                    recipients=[player.name],
                )
        votes = {
            player.name: getattr(decision, "vote", None)
            for player, decision in zip(alive, decisions, strict=True)
        }
        voted_out, count = majority_vote(
            votes,
            valid_targets=[player.name for player in alive],
            rng=self.rng,
        )
        shot: str | None = None
        hunter = next(
            (
                player
                for player in alive
                if player.name == voted_out and player.role == "猎人"
            ),
            None,
        )
        if hunter is not None:
            targets = [player for player in alive if player.name != hunter.name]
            action = await self.runtime.decide(
                game.id,
                hunter.name,
                "你被投票淘汰，是否开枪",
                hunter_model([player.name for player in targets]),
            )
            if action is not None:
                await self.events.emit(
                    game,
                    "hunter_action",
                    {"player": hunter.name, **action.model_dump()},
                    visibility=Visibility.PRIVATE,
                    recipients=[hunter.name],
                )
            if getattr(action, "shoot", False):
                shot = getattr(action, "target", None)
        for player in game.players:
            if player.name in {voted_out, shot}:
                player.eliminate()
        await self.repository.save_game(game)
        await self.events.emit(
            game,
            "vote_result",
            {"voted_out": voted_out, "votes": count, "hunter_shot": shot},
        )

    async def _finish_if_won(self, game: GameState) -> bool:
        winner = check_winner(game.players)
        if winner is None:
            return False
        await self._finish(game, GameStatus.COMPLETED, winner)
        return True

    async def _finish(self, game: GameState, status: GameStatus, winner: str) -> None:
        game.status = status
        game.phase = Phase.FINISHED
        game.winner = winner
        game.finished_at = datetime.now(UTC)
        await self.repository.save_game(game)
        await self.events.emit(
            game,
            "roles_revealed",
            {
                "players": [
                    {"player": player.name, "role": player.role}
                    for player in game.players
                ]
            },
        )
        await self.events.emit(game, "game_finished", {"winner": winner})
        await self.events.broker.close_game(game.id)

    async def _discuss(
        self,
        game: GameState,
        players: list[GamePlayer],
        announcement: str,
        *,
        discussion_kind: str,
        rounds: int,
        visibility: Visibility = Visibility.PUBLIC,
        recipients: list[str] | None = None,
    ) -> None:
        recipient_names = recipients or []
        names = [player.name for player in players]
        await self.events.emit(
            game,
            "discussion_started",
            {
                "discussion_kind": discussion_kind,
                "round": game.round_number,
                "participants": names,
            },
            visibility=visibility,
            recipients=recipient_names,
        )
        async for activity in self.runtime.discuss(
            game.id,
            names,
            announcement,
            rounds,
        ):
            payload: dict[str, object] = {
                "player": activity.player,
                "round": game.round_number,
                "discussion_round": activity.discussion_round,
                "discussion_kind": discussion_kind,
            }
            if activity.kind == "speech":
                payload["content"] = activity.content or ""
            await self.events.emit(
                game,
                "speaker_turn_started" if activity.kind == "turn_started" else "speech",
                payload,
                visibility=visibility,
                recipients=recipient_names,
            )
