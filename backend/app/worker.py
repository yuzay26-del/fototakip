"""Arka plan işçisi iskeleti.

Faz 1'de iş yapmaz; yalnızca ayakta kaldığını gösterir. Görevler eklendiğinde
kuyruk adaptörü üzerinden mesaj tüketecek.
"""

import asyncio
import logging

from app.core.config import get_settings

logger = logging.getLogger("fototakip.worker")


async def run() -> None:
    settings = get_settings()
    logger.info("Worker başladı (kuyruk: %s)", settings.queue_backend)
    while True:
        await asyncio.sleep(60)
        logger.debug("Worker ayakta")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run())
