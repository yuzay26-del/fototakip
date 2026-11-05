from typing import Any

from app.adapters.queue.base import Handler


class InProcessQueue:
    """Süreç içi asyncio kuyruğu (termux modu). Faz 1'de yalnızca iskelet."""

    def __init__(self) -> None:
        self._handlers: dict[str, Handler] = {}

    def register(self, task_name: str, handler: Handler) -> None:
        self._handlers[task_name] = handler

    async def enqueue(self, task_name: str, payload: dict[str, Any]) -> None:
        raise NotImplementedError
