"""FotoTakip: fotoğraf tabanlı saha iş takibi."""

import os

__version__ = "0.7.1"


def web_dir() -> str:
    """Arayüz klasörü (web/). APK'da Python dosyaları diskte olmadığı için yolu FOTOTAKIP_WEB verir."""
    return os.environ.get("FOTOTAKIP_WEB") or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")
