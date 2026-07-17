from __future__ import annotations

from werewolf_game.infrastructure.metrics import PrometheusMetrics


def test_prometheus_metrics_expose_only_low_cardinality_labels() -> None:
    metrics = PrometheusMetrics()
    metrics.game_started()
    metrics.game_finished("completed")
    metrics.review_started()
    metrics.review_finished("completed")
    metrics.model_call("structured_decision", "success", 0.25)
    metrics.model_retry("structured_decision")
    metrics.sse_connected()
    metrics.sse_disconnected()
    body, content_type = metrics.render()
    text = body.decode()
    assert 'werewolf_games_finished_total{status="completed"}' in text
    assert 'operation="structured_decision"' in text
    assert "werewolf_model_retries_total" in text
    assert "game_id" not in text
    assert content_type.startswith("text/plain")
