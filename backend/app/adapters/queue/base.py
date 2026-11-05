from collections.abc import Awaitable, Callable
from typing import Any, Protocol

Handler = Callable[[dict[str, Any]], Awaitable[None]]


class QueueBackend(Protocol):
    """Arka plan görev kuyruğu (küçük resim üretimi vb.)."""

    async def enqueue(self, task_name: str, payload: dict[str, Any]) -> None: ...

    def register(self, task_name: str, handler: Handler) -> None: ...
