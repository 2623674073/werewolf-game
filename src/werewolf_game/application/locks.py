from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass


@dataclass(slots=True)
class _LockEntry:
    lock: asyncio.Lock
    users: int = 0


class GameOperationLocks:
    """Serialize lifecycle operations that target the same game."""

    def __init__(self) -> None:
        self._guard = asyncio.Lock()
        self._entries: dict[str, _LockEntry] = {}

    @asynccontextmanager
    async def hold(self, game_id: str) -> AsyncIterator[None]:
        async with self._guard:
            entry = self._entries.setdefault(game_id, _LockEntry(asyncio.Lock()))
            entry.users += 1
        acquired = False
        try:
            await entry.lock.acquire()
            acquired = True
            yield
        finally:
            if acquired:
                entry.lock.release()
            async with self._guard:
                entry.users -= 1
                if entry.users == 0:
                    self._entries.pop(game_id, None)
