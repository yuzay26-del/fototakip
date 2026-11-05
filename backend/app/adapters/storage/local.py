from pathlib import Path


class LocalStorage:
    """Yerel klasör deposu (termux modu). Faz 1'de yalnızca iskelet."""

    def __init__(self, root: Path) -> None:
        self.root = root

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        raise NotImplementedError

    async def get(self, key: str) -> bytes:
        raise NotImplementedError

    async def delete(self, key: str) -> None:
        raise NotImplementedError

    async def url_for(self, key: str, expires_in: int = 3600) -> str:
        raise NotImplementedError
