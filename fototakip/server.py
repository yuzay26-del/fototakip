"""HTTP sunucusu: yönlendirme, statik dosyalar, çerez oturumu ve canlı olaylar (SSE)."""

from __future__ import annotations

import json
import mimetypes
import os
import queue
import shutil
import threading
import traceback
from dataclasses import dataclass
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlsplit

from . import api, auth, db, geo, tunnel

COOKIE = "ft_session"


@dataclass
class Config:
    host: str = "0.0.0.0"
    port: int = 8080
    data_dir: str = "./data"
    web_dir: str = ""
    max_upload_mb: int = 15
    quiet: bool = False
    geocoder: str = "on"          # "off" ya da başka bir Nominatim uyumlu adres
    geocoder_contact: str = ""    # isteğe bağlı: Nominatim'e kendini tanıtmak için e-posta

    @property
    def db_path(self) -> str:
        return os.path.join(self.data_dir, "fototakip.db")


class EventBus:
    """Her açık tarayıcı sekmesi için bir kuyruk; değişiklik olunca hepsine haber verir."""

    def __init__(self):
        self._subs: set[queue.Queue] = set()
        self._lock = threading.Lock()

    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=100)
        with self._lock:
            self._subs.add(q)
        return q

    def unsubscribe(self, q: queue.Queue):
        with self._lock:
            self._subs.discard(q)

    def publish(self, event: dict):
        with self._lock:
            subs = list(self._subs)
        for q in subs:
            try:
                q.put_nowait(event)
            except queue.Full:
                pass

    @property
    def count(self) -> int:
        return len(self._subs)


class FileResponse:
    def __init__(self, path, mime, immutable=False, download=None, cleanup=None):
        self.path, self.mime, self.immutable, self.download, self.cleanup = path, mime, immutable, download, cleanup


class Request:
    def __init__(self, handler: "Handler", con, user, token, match, query):
        self.h, self.con, self.user, self.token = handler, con, user, token
        self.match, self.query = match, query
        self.cfg: Config = handler.server.cfg
        self.geo: geo.Geocoder = handler.server.geo
        self.tunnel: tunnel.Tunnel = handler.server.tunnel
        self.set_cookie: str | None = None
        self._body: bytes | None = None
        self._events: list[dict] = []

    def body(self, limit: int = 1024 * 1024) -> bytes:
        if self._body is None:
            try:
                length = int(self.h.headers.get("Content-Length") or 0)
            except ValueError:
                raise api.ApiError(400, "bad_length", "Content-Length geçersiz.")
            if length > limit:
                raise api.ApiError(413, "too_large", f"Dosya çok büyük. Sınır {limit // (1024 * 1024)} MB.")
            self._body = self.h.rfile.read(length) if length else b""
            self.h._consumed = True
        return self._body

    def json(self) -> dict:
        raw = self.body()
        if not raw:
            return {}
        try:
            data = json.loads(raw)
        except ValueError:
            raise api.ApiError(400, "bad_json", "Gövde geçerli JSON değil.")
        if not isinstance(data, dict):
            raise api.ApiError(400, "bad_json", "Gövde bir JSON nesnesi olmalı.")
        return data

    def file(self, path, mime, **kw) -> FileResponse:
        if not os.path.isfile(path):
            raise api.ApiError(404, "not_found", "Dosya bulunamadı.")
        return FileResponse(path, mime, **kw)

    def publish(self, event: dict):
        self._events.append({**event, "by": self.user["id"] if self.user else None})


class Handler(BaseHTTPRequestHandler):
    server_version = "FotoTakip"
    protocol_version = "HTTP/1.1"

    # ---- yardımcılar ----
    def log_message(self, fmt, *args):
        if not self.server.cfg.quiet:
            super().log_message(fmt, *args)

    def _token(self) -> str | None:
        authz = self.headers.get("Authorization", "")
        if authz.startswith("Bearer "):
            return authz[7:].strip()
        raw = self.headers.get("Cookie")
        if raw:
            c = SimpleCookie()
            try:
                c.load(raw)
            except Exception:
                return None
            if COOKIE in c:
                return c[COOKIE].value
        return None

    def _https(self) -> bool:
        # Tünel (cloudflared) üzerinden gelen istek HTTPS'tir; çerez yalnızca HTTPS'te gönderilsin.
        return self.headers.get("X-Forwarded-Proto", "").lower() == "https" or '"https"' in self.headers.get("Cf-Visitor", "")

    def _security_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")  # OSM karo sunucusu kaynağı görmek ister
        self.send_header("X-Frame-Options", "DENY")

    def _send_json(self, status: int, payload, cookie: str | None = None):
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if cookie is not None:
            if cookie:
                secure = "; Secure" if self._https() else ""
                self.send_header("Set-Cookie", f"{COOKIE}={cookie}; Path=/; HttpOnly; SameSite=Lax; Max-Age={auth.SESSION_DAYS * 86400}{secure}")
            else:
                self.send_header("Set-Cookie", f"{COOKIE}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0")
        self._security_headers()
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _send_error(self, e: api.ApiError):
        self._send_json(e.status, {"error": {"code": e.code, "message": e.message, **e.extra}})

    def _send_file(self, f: FileResponse):
        try:
            size = os.path.getsize(f.path)
            self.send_response(200)
            self.send_header("Content-Type", f.mime)
            self.send_header("Content-Length", str(size))
            self.send_header("Cache-Control", "private, max-age=31536000, immutable" if f.immutable else "no-cache")
            if f.mime == "image/svg+xml":
                self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'")
            if f.download:
                self.send_header("Content-Disposition", f'attachment; filename="{f.download}"')
            self._security_headers()
            self.end_headers()
            if self.command != "HEAD":
                with open(f.path, "rb") as fh:
                    shutil.copyfileobj(fh, self.wfile)
        finally:
            if f.cleanup:
                shutil.rmtree(f.cleanup, ignore_errors=True)

    # ---- statik ----
    def _static(self, path: str) -> bool:
        web = self.server.cfg.web_dir
        rel = unquote(path).lstrip("/") or "index.html"
        full = os.path.realpath(os.path.join(web, rel))
        if not full.startswith(os.path.realpath(web) + os.sep) or not os.path.isfile(full):
            if "." in os.path.basename(rel):
                return False
            full = os.path.join(web, "index.html")  # tek sayfa uygulama
        mime = mimetypes.guess_type(full)[0] or "application/octet-stream"
        if full.endswith(".webmanifest"):
            mime = "application/manifest+json"
        if mime.startswith("text/") or mime in ("application/javascript", "application/manifest+json"):
            mime += "; charset=utf-8"
        with open(full, "rb") as fh:
            body = fh.read()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        if full.endswith("sw.js"):
            self.send_header("Service-Worker-Allowed", "/")
        self._security_headers()
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)
        return True

    # ---- canlı olaylar ----
    def _events(self, con):
        user = auth.user_for_token(con, self._token())
        con.close()
        if not user:
            self._send_error(api.ApiError(401, "unauthorized", "Oturum açman gerekiyor."))
            return
        bus: EventBus = self.server.bus
        q = bus.subscribe()
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Accel-Buffering", "no")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            self.wfile.write(b"retry: 3000\n\n")
            self.wfile.flush()
            while not self.server.stopping.is_set():
                try:
                    ev = q.get(timeout=15)
                    self.wfile.write(f"data: {json.dumps(ev)}\n\n".encode())
                except queue.Empty:
                    self.wfile.write(b": ping\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            bus.unsubscribe(q)
            self.close_connection = True

    # ---- yönlendirme ----
    def _dispatch(self):
        parts = urlsplit(self.path)
        path = parts.path
        query = {k: v[0] for k, v in parse_qs(parts.query).items()}
        cfg: Config = self.server.cfg
        self._consumed = False
        con = db.connect(cfg.db_path)
        if path == "/api/events" and self.command == "GET":
            self._events(con)
            return
        try:
            for method, pattern, fn, needs_auth in api.ROUTES:
                if method != self.command and not (method == "GET" and self.command == "HEAD"):
                    continue
                m = pattern.match(path)
                if not m:
                    continue
                token = self._token()
                user = auth.user_for_token(con, token) if token else None
                if needs_auth and not user:
                    raise api.ApiError(401, "unauthorized", "Oturum açman gerekiyor.")
                req = Request(self, con, user, token, m.groupdict(), query)
                result = fn(req)
                self._drain()
                for ev in req._events:
                    self.server.bus.publish(ev)
                if isinstance(result, FileResponse):
                    self._send_file(result)
                else:
                    self._send_json(200, result, cookie=req.set_cookie)
                return
            if path.startswith("/api/") or path.startswith("/files/"):
                raise api.ApiError(404, "not_found", "Böyle bir uç nokta yok.")
            if self.command in ("GET", "HEAD") and self._static(path):
                return
            raise api.ApiError(404, "not_found", "Sayfa bulunamadı.")
        except api.ApiError as e:
            self._drain()
            self._send_error(e)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception:
            traceback.print_exc()
            self._drain()
            self._send_error(api.ApiError(500, "server_error", "Sunucuda beklenmeyen bir hata oldu. Kayıtlara bak."))
        finally:
            con.close()

    def _drain(self):
        """Okunmamış gövdeyi tüket ki bağlantı bozulmasın (büyük dosya reddi gibi durumlar)."""
        if getattr(self, "_consumed", False):
            return
        self._consumed = True
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length and length <= 64 * 1024 * 1024:
            try:
                self.rfile.read(length)
            except Exception:
                pass
        elif length:
            self.close_connection = True

    def do_GET(self):
        self._dispatch()

    def do_HEAD(self):
        self._dispatch()

    def do_POST(self):
        self._dispatch()

    def do_PATCH(self):
        self._dispatch()

    def do_DELETE(self):
        self._dispatch()


class FotoTakipServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.bus = EventBus()
        self.stopping = threading.Event()
        self.geo = geo.Geocoder(cfg.db_path, cfg.geocoder, publish=self.bus.publish, contact=cfg.geocoder_contact)
        super().__init__((cfg.host, cfg.port), Handler)
        self.tunnel = tunnel.Tunnel(self.server_address[1])

    def shutdown(self):
        self.stopping.set()
        self.geo.stop()
        self.tunnel.stop()
        super().shutdown()


def make_server(cfg: Config) -> FotoTakipServer:
    os.makedirs(cfg.data_dir, exist_ok=True)
    os.makedirs(os.path.join(cfg.data_dir, "photos"), exist_ok=True)
    if not cfg.web_dir:
        cfg.web_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")
    db.init(cfg.db_path)
    return FotoTakipServer(cfg)
