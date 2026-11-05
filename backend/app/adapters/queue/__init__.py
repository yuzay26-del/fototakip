from app.adapters.queue.base import QueueBackend
from app.adapters.queue.inprocess import InProcessQueue
from app.core.config import Settings


def get_queue(settings: Settings) -> QueueBackend:
    backends = {
        "inprocess": InProcessQueue,
    }
    try:
        return backends[settings.queue_backend]()
    except KeyError:
        raise NotImplementedError(
            f"QUEUE_BACKEND={settings.queue_backend} henüz uygulanmadı"
        ) from None


__all__ = ["InProcessQueue", "QueueBackend", "get_queue"]
