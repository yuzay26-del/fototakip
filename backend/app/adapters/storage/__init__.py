from app.adapters.storage.base import StorageBackend
from app.adapters.storage.local import LocalStorage
from app.core.config import Settings


def get_storage(settings: Settings) -> StorageBackend:
    backends = {
        "local": lambda: LocalStorage(settings.media_root),
    }
    try:
        return backends[settings.storage_backend]()
    except KeyError:
        raise NotImplementedError(
            f"STORAGE_BACKEND={settings.storage_backend} henüz uygulanmadı"
        ) from None


__all__ = ["LocalStorage", "StorageBackend", "get_storage"]
