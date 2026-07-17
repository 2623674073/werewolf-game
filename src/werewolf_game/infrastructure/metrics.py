from __future__ import annotations

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

ACTIVE_GAMES = Gauge("werewolf_active_games", "Currently running games")
GAME_RESULTS = Counter(
    "werewolf_games_finished_total",
    "Finished games by terminal status",
    ["status"],
)
ACTIVE_REVIEWS = Gauge("werewolf_active_reviews", "Currently running historian jobs")
REVIEW_RESULTS = Counter(
    "werewolf_reviews_finished_total",
    "Finished historian jobs by status",
    ["status"],
)
MODEL_CALLS = Counter(
    "werewolf_model_calls_total",
    "Model calls by operation and outcome",
    ["operation", "outcome"],
)
MODEL_LATENCY = Histogram(
    "werewolf_model_call_duration_seconds",
    "Model call latency by operation",
    ["operation"],
    buckets=(0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60, 120),
)
MODEL_RETRIES = Counter(
    "werewolf_model_retries_total",
    "Model retries by operation",
    ["operation"],
)
ACTIVE_SSE = Gauge("werewolf_sse_connections", "Currently open SSE connections")


class PrometheusMetrics:
    def game_started(self) -> None:
        ACTIVE_GAMES.inc()

    def game_finished(self, status: str) -> None:
        ACTIVE_GAMES.dec()
        GAME_RESULTS.labels(status=status).inc()

    def review_started(self) -> None:
        ACTIVE_REVIEWS.inc()

    def review_finished(self, status: str) -> None:
        ACTIVE_REVIEWS.dec()
        REVIEW_RESULTS.labels(status=status).inc()

    def model_call(self, operation: str, outcome: str, seconds: float) -> None:
        MODEL_CALLS.labels(operation=operation, outcome=outcome).inc()
        MODEL_LATENCY.labels(operation=operation).observe(seconds)

    def model_retry(self, operation: str) -> None:
        MODEL_RETRIES.labels(operation=operation).inc()

    def sse_connected(self) -> None:
        ACTIVE_SSE.inc()

    def sse_disconnected(self) -> None:
        ACTIVE_SSE.dec()

    @staticmethod
    def render() -> tuple[bytes, str]:
        return generate_latest(), CONTENT_TYPE_LATEST
