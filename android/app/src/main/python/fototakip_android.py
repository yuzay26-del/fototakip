"""APK içindeki giriş noktası: FotoTakip sunucusunu Termux olmadan, Android servisinin içinde çalıştırır.

Java tarafı (ServerService) start() ve stop() çağırır. Sunucu kodu Termux sürümüyle aynıdır;
yalnızca klasörler ve cloudflared yolu Android'in verdiği yerlerden gelir.
"""

from __future__ import annotations

import os
import tempfile
import threading

from fototakip import __version__
from fototakip.__main__ import autostart_tunnel, ensure_setup_code, lan_addresses
from fototakip.api import setup_code_file
from fototakip.server import Config, make_server

_lock = threading.Lock()
_server = None
_cfg: Config | None = None


def start(files_dir: str, cache_dir: str, web_dir: str, cloudflared: str, port: int) -> str:
    """Sunucuyu arka planda başlatır; tünel notunu döndürür. Port doluysa OSError fırlatır."""
    global _server, _cfg
    with _lock:
        if _server is not None:
            return ""
        os.environ["HOME"] = files_dir                 # cloudflared ~/.cloudflared kullanır
        os.environ["TMPDIR"] = cache_dir
        tempfile.tempdir = cache_dir                   # yedek zip'i buraya yazılır
        if cloudflared and os.path.exists(cloudflared):
            os.environ["FOTOTAKIP_CLOUDFLARED"] = cloudflared
        # Android'de /etc/resolv.conf yok; Go'nun DNS'i sistem çözücüsünü kullansın.
        os.environ.setdefault("GODEBUG", "netdns=cgo")
        cfg = Config(host="0.0.0.0", port=int(port), data_dir=os.path.join(files_dir, "fototakip-data"),
                     web_dir=web_dir, quiet=True)
        server = make_server(cfg)
        ensure_setup_code(cfg)
        note = autostart_tunnel(server, cfg)
        threading.Thread(target=_serve, args=(server,), daemon=True, name="fototakip-http").start()
        _server, _cfg = server, cfg
        return note


def _serve(server):
    try:
        server.serve_forever()
    finally:
        server.stopping.set()
        server.server_close()


def stop() -> None:
    global _server
    with _lock:
        server, _server = _server, None
    if server is not None:
        server.shutdown()


def running() -> bool:
    return _server is not None


def setup_code() -> str:
    """İlk kurulum bitmediyse kurulum kodunu döndürür (kurulumdan sonra dosya silinir)."""
    if _cfg is None:
        return ""
    try:
        with open(setup_code_file(_cfg), encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def lan_urls() -> list:
    server = _server
    if server is None:
        return []
    return [f"http://{a}:{server.server_address[1]}" for a in lan_addresses()]


def version() -> str:
    return __version__
