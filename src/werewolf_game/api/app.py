from __future__ import annotations

import asyncio
import hmac
import json
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, FastAPI, Header, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles

from werewolf_game.api.schemas import (
    CreateGameRequest,
    EventResponse,
    GameResponse,
    GameReviewResponse,
    SessionResponse,
)
from werewolf_game.application.engine import GameEngine
from werewolf_game.application.errors import (
    ApplicationError,
    CapacityError,
    ConflictError,
    NotFoundError,
)
from werewolf_game.application.events import EventBroker, EventCoordinator
from werewolf_game.application.review_service import GameReviewService
from werewolf_game.application.service import GameService
from werewolf_game.config import Settings
from werewolf_game.domain.models import GameEvent, GameState, GameStatus
from werewolf_game.domain.reviews import GameReview
from werewolf_game.infrastructure.agentscope_runtime import (
    AgentScopeRuntime,
    build_openai_compatible_model,
)
from werewolf_game.infrastructure.database import Database
from werewolf_game.infrastructure.historian import McpGameHistorian
from werewolf_game.infrastructure.logging import request_id_var
from werewolf_game.infrastructure.repository import SqliteGameRepository


@dataclass(slots=True)
class AppComponents:
    settings: Settings
    database: Database
    repository: SqliteGameRepository
    broker: EventBroker
    service: GameService
    review_service: GameReviewService | None = None
    historian: McpGameHistorian | None = None


class ApiError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message


security = HTTPBearer(auto_error=False)
logger = logging.getLogger(__name__)


def build_components(settings: Settings | None = None) -> AppComponents:
    settings = settings or Settings()  # type: ignore[call-arg]
    database = Database(settings.database_url)
    repository = SqliteGameRepository(database.session_factory)
    broker = EventBroker()
    model = build_openai_compatible_model(
        api_key=settings.llm_api_key.get_secret_value(),
        model_name=settings.llm_model_id,
        base_url=settings.llm_base_url,
        timeout_seconds=settings.llm_timeout,
        max_retries=settings.model_max_retries,
    )
    runtime = AgentScopeRuntime(
        model=model,
        max_model_concurrency=settings.max_model_concurrency,
        timeout_seconds=settings.llm_timeout,
        max_retries=0,
    )
    historian = McpGameHistorian(execution_timeout=settings.historian_timeout)
    events = EventCoordinator(repository, broker)
    service = GameService(
        repository,
        lambda: GameEngine(runtime, repository, events),
        max_concurrent_games=settings.max_concurrent_games,
        events=events,
    )
    review_service = GameReviewService(repository, historian)
    return AppComponents(
        settings,
        database,
        repository,
        broker,
        service,
        review_service,
        historian,
    )


def create_app(components: AppComponents | None = None) -> FastAPI:
    components = components or build_components()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        await components.repository.mark_running_interrupted()
        await components.repository.mark_pending_reviews_failed("service_restarted")
        try:
            yield
        finally:
            try:
                await components.service.shutdown()
            finally:
                if components.review_service is not None:
                    await components.review_service.shutdown()
                try:
                    if components.historian is not None:
                        await components.historian.close()
                finally:
                    await components.database.dispose()

    app = FastAPI(title="Werewolf Game API", version="0.2.0", lifespan=lifespan)
    app.state.components = components
    app.add_middleware(
        CORSMiddleware,
        allow_origins=components.settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "Last-Event-ID",
            "X-Request-ID",
        ],
    )

    @app.middleware("http")
    async def request_id_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request.state.request_id = request.headers.get("X-Request-ID") or str(uuid4())
        token = request_id_var.set(request.state.request_id)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request.state.request_id
            return response
        finally:
            request_id_var.reset(token)

    @app.exception_handler(ApiError)
    async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
        return _error_response(request, exc.status_code, exc.code, exc.message)

    @app.exception_handler(ApplicationError)
    async def application_error_handler(
        request: Request, exc: ApplicationError
    ) -> JSONResponse:
        status = 500
        if isinstance(exc, NotFoundError):
            status = 404
        elif isinstance(exc, ConflictError):
            status = 409
        elif isinstance(exc, CapacityError):
            status = 429
        return _error_response(request, status, exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, _: RequestValidationError
    ) -> JSONResponse:
        return _error_response(request, 422, "validation_error", "请求参数不合法")

    @app.exception_handler(Exception)
    async def unexpected_error_handler(request: Request, _: Exception) -> JSONResponse:
        return _error_response(request, 500, "internal_error", "服务器内部错误")

    async def require_token(
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    ) -> None:
        expected = components.settings.app_api_token.get_secret_value()
        supplied = credentials.credentials if credentials is not None else ""
        if (
            credentials is None
            or credentials.scheme.lower() != "bearer"
            or not hmac.compare_digest(supplied, expected)
        ):
            raise ApiError(401, "unauthorized", "认证失败")

    router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_token)])

    @router.get("/session", response_model=SessionResponse)
    async def get_session() -> SessionResponse:
        return SessionResponse(
            capabilities=["control", "public_view", "god_view"],
        )

    @router.post(
        "/games",
        status_code=201,
        response_model=GameResponse,
        response_model_exclude_none=True,
    )
    async def create_game(body: CreateGameRequest) -> GameResponse:
        return _game_response(
            await components.service.create_game(body.player_count), god_view=False
        )

    @router.post(
        "/games/{game_id}/start",
        status_code=202,
        response_model=GameResponse,
        response_model_exclude_none=True,
    )
    async def start_game(game_id: str) -> GameResponse:
        return _game_response(
            await components.service.start_game(game_id), god_view=False
        )

    @router.post(
        "/games/{game_id}/cancel",
        status_code=202,
        response_model=GameResponse,
        response_model_exclude_none=True,
    )
    async def cancel_game(game_id: str) -> GameResponse:
        return _game_response(
            await components.service.cancel_game(game_id), god_view=False
        )

    @router.get(
        "/games",
        response_model=list[GameResponse],
        response_model_exclude_none=True,
    )
    async def list_games(
        offset: Annotated[int, Query(ge=0)] = 0,
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
    ) -> list[GameResponse]:
        games = await components.repository.list_games(offset, limit)
        return [_game_response(game, god_view=False) for game in games]

    @router.get(
        "/games/{game_id}",
        response_model=GameResponse,
        response_model_exclude_none=True,
    )
    async def get_game(
        game_id: str,
        view: Literal["public", "god"] = "public",
    ) -> GameResponse:
        return _game_response(
            await components.service.require_game(game_id), god_view=view == "god"
        )

    @router.get("/games/{game_id}/events", response_model=list[EventResponse])
    async def list_events(
        game_id: str,
        after_seq: Annotated[int, Query(ge=0)] = 0,
        view: Literal["public", "god"] = "public",
    ) -> list[EventResponse]:
        await components.service.require_game(game_id)
        events = await components.repository.list_events(
            game_id, after_seq, view == "god"
        )
        return [_event_response(event) for event in events]

    @router.post(
        "/games/{game_id}/review",
        status_code=202,
        response_model=GameReviewResponse,
        response_model_exclude_none=True,
    )
    async def create_game_review(game_id: str) -> GameReviewResponse:
        if components.review_service is None:
            raise ApiError(503, "review_service_unavailable", "复盘服务不可用")
        return _review_response(await components.review_service.request_review(game_id))

    @router.get(
        "/games/{game_id}/review",
        response_model=GameReviewResponse,
        response_model_exclude_none=True,
    )
    async def get_game_review(game_id: str) -> GameReviewResponse:
        if components.review_service is None:
            raise ApiError(503, "review_service_unavailable", "复盘服务不可用")
        return _review_response(await components.review_service.get_review(game_id))

    @router.get("/games/{game_id}/stream")
    async def stream_events(
        game_id: str,
        view: Literal["public", "god"] = "public",
        last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
    ) -> StreamingResponse:
        game = await components.service.require_game(game_id)
        try:
            after_seq = int(last_event_id or "0")
        except ValueError as exc:
            raise ApiError(
                422, "invalid_last_event_id", "Last-Event-ID 必须是整数"
            ) from exc
        if after_seq < 0:
            raise ApiError(422, "invalid_last_event_id", "Last-Event-ID 不能为负数")
        return StreamingResponse(
            _event_stream(components, game, after_seq, view == "god"),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    app.include_router(router)

    @app.get("/health/live")
    async def live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready")
    async def ready() -> JSONResponse:
        if await components.repository.ping():
            return JSONResponse({"status": "ready"})
        return JSONResponse({"status": "not_ready"}, status_code=503)

    _mount_web_app(app, components.settings)

    return app


async def _event_stream(
    components: AppComponents,
    game: GameState,
    after_seq: int,
    include_private: bool,
) -> AsyncIterator[str]:
    live = components.broker.subscribe(game.id, include_private=include_private)
    pending: asyncio.Future[GameEvent] = asyncio.ensure_future(anext(live))
    await asyncio.sleep(0)
    last_seq = after_seq
    try:
        history = await components.repository.list_events(
            game.id, after_seq, include_private
        )
        for event in history:
            last_seq = max(last_seq, event.seq)
            yield _sse(event)
        terminal_event_types = {
            "game_finished",
            "game_cancelled",
            "game_interrupted",
            "game_failed",
        }
        if any(event.type in terminal_event_types for event in history):
            return
        if game.status not in {GameStatus.CREATED, GameStatus.RUNNING}:
            # A terminal snapshot may become visible just before its final event is
            # committed. Give that short transaction window one final database read,
            # while still allowing legacy terminal games without a closing event.
            await asyncio.sleep(0.05)
            tail = await components.repository.list_events(
                game.id, last_seq, include_private
            )
            for trailing_event in tail:
                if trailing_event.seq > last_seq:
                    last_seq = trailing_event.seq
                    yield _sse(trailing_event)
            return
        while True:
            try:
                event = await asyncio.wait_for(asyncio.shield(pending), timeout=15)
            except TimeoutError:
                yield ": keep-alive\n\n"
                continue
            except StopAsyncIteration:
                tail = await components.repository.list_events(
                    game.id, last_seq, include_private
                )
                for trailing_event in tail:
                    if trailing_event.seq > last_seq:
                        last_seq = trailing_event.seq
                        yield _sse(trailing_event)
                return
            if event.seq > last_seq:
                last_seq = event.seq
                yield _sse(event)
            pending = asyncio.ensure_future(anext(live))
    finally:
        pending.cancel()
        with suppress(asyncio.CancelledError, StopAsyncIteration):
            await pending
        await live.aclose()


def _sse(event: GameEvent) -> str:
    data = json.dumps(
        _event_response(event).model_dump(mode="json"),
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return f"id: {event.seq}\nevent: {event.type}\ndata: {data}\n\n"


def _game_response(game: GameState, *, god_view: bool) -> GameResponse:
    players: list[dict[str, object]] = []
    reveal_roles = god_view or game.status in {GameStatus.COMPLETED, GameStatus.DRAW}
    for player in game.players:
        item: dict[str, object] = {
            "name": player.name,
            "character": player.character,
            "is_alive": player.is_alive,
            "persona_tags": player.persona_tags,
        }
        if reveal_roles:
            item.update(
                role=player.role,
                has_antidote=player.has_antidote,
                has_poison=player.has_poison,
            )
        players.append(item)
    return GameResponse(
        id=game.id,
        player_count=game.player_count,
        status=game.status.value,
        phase=game.phase.value,
        round_number=game.round_number,
        players=players,  # type: ignore[arg-type]
        winner=game.winner,
        error_code=game.error_code,
        created_at=game.created_at.isoformat(),
        started_at=game.started_at.isoformat() if game.started_at else None,
        finished_at=game.finished_at.isoformat() if game.finished_at else None,
    )


def _review_response(review: GameReview) -> GameReviewResponse:
    return GameReviewResponse(
        game_id=review.game_id,
        status=review.status.value,
        result=review.result,
        error_code=review.error_code,
        created_at=review.created_at.isoformat(),
        completed_at=(
            review.completed_at.isoformat() if review.completed_at is not None else None
        ),
    )


def _event_response(event: GameEvent) -> EventResponse:
    return EventResponse(
        game_id=event.game_id,
        seq=event.seq,
        type=event.type,  # type: ignore[arg-type]
        phase=event.phase.value,
        visibility=event.visibility.value,
        recipients=list(event.recipients),
        payload=event.payload,
        created_at=event.created_at.isoformat(),
    )


def _mount_web_app(app: FastAPI, settings: Settings) -> None:
    dist = Path(settings.web_dist_dir)
    if not dist.is_absolute():
        dist = Path.cwd() / dist
    index = dist / "index.html"
    assets = dist / "assets"
    if not index.is_file():
        logger.warning("frontend build not found", extra={"web_dist_dir": str(dist)})
        return
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="web-assets")

    @app.get("/{web_path:path}", include_in_schema=False)
    async def web_app(web_path: str) -> Response:
        candidate = (dist / web_path).resolve()
        if candidate.is_relative_to(dist.resolve()) and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index)


def _error_response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", str(uuid4()))
    return JSONResponse(
        {"error": {"code": code, "message": message, "request_id": request_id}},
        status_code=status_code,
    )
