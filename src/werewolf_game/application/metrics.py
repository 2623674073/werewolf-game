from __future__ import annotations

from typing import Protocol


class ApplicationMetrics(Protocol):
    def game_started(self) -> None: ...

    def game_finished(self, status: str) -> None: ...

    def review_started(self) -> None: ...

    def review_finished(self, status: str) -> None: ...

    def model_call(self, operation: str, outcome: str, seconds: float) -> None: ...

    def model_retry(self, operation: str) -> None: ...

    def sse_connected(self) -> None: ...

    def sse_disconnected(self) -> None: ...


class NullMetrics:
    def game_started(self) -> None:
        return None

    def game_finished(self, status: str) -> None:
        del status

    def review_started(self) -> None:
        return None

    def review_finished(self, status: str) -> None:
        del status

    def model_call(self, operation: str, outcome: str, seconds: float) -> None:
        del operation, outcome, seconds

    def model_retry(self, operation: str) -> None:
        del operation

    def sse_connected(self) -> None:
        return None

    def sse_disconnected(self) -> None:
        return None
