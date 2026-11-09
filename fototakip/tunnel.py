"""Dışarıdan güvenli erişim: ücretsiz Cloudflare tüneli ve Termux DNS ayarı.

İki tünel türü:
  quick  Hızlı tünel. Hesap gerekmez, ücretsiz. Adres https://….trycloudflare.com biçimindedir
         ve her başlatmada değişir. Cloudflare bunu deneme amaçlı sunar, çalışma süresi garantisi yoktur.
  named  Adlandırılmış tünel. Ücretsiz Cloudflare hesabı ve Cloudflare'de yönetilen bir alan adı
         gerekir. Adres sabittir (ör. https://is.alanadin.com). Zero Trust panelinden alınan token girilir.

Bağlantı telefondan dışarıya doğru açılır; modemde port açmak gerekmez, mobil ağda (CGNAT) da çalışır.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import threading
import time
from collections import deque

QUICK_RE = re.compile(r"https://[-a-z0-9]+\.trycloudflare\.com")
READY_RE = re.compile(r"Registered tunnel connection|Connection [0-9a-f-]+ registered", re.I)
DNS_PRESETS = {
    "opendns": ("OpenDNS", ["208.67.222.222", "208.67.220.220"]),
    "cloudflare": ("Cloudflare", ["1.1.1.1", "1.0.0.1"]),
    "google": ("Google", ["8.8.8.8", "8.8.4.4"]),
    "quad9": ("Quad9", ["9.9.9.9", "149.112.112.112"]),
}


def cloudflared_path() -> str | None:
    return os.environ.get("FOTOTAKIP_CLOUDFLARED") or shutil.which("cloudflared")


class Tunnel:
    def __init__(self, port: int):
        self.port = port
        self.proc: subprocess.Popen | None = None
        self.mode = "off"
        self.status = "stopped"      # stopped | starting | running | error
        self.url = ""
        self.error = ""
        self.started_at = 0.0
        self.log: deque[str] = deque(maxlen=40)
        self._secret = ""
        self._lock = threading.Lock()

    def _scrub(self, line: str) -> str:
        if self._secret:
            line = line.replace(self._secret, "•••")
        return re.sub(r"(token[=:\s]+)\S+", r"\1•••", line, flags=re.I)[:300]

    def snapshot(self) -> dict:
        return {"mode": self.mode, "status": self.status, "url": self.url, "error": self.error,
                "started_at": self.started_at, "log": list(self.log)[-15:],
                "cloudflared": cloudflared_path(), "pid": self.proc.pid if self.proc and self.proc.poll() is None else None}

    def start(self, mode: str, token: str = "", hostname: str = "") -> dict:
        with self._lock:
            self._stop_locked()
            binary = cloudflared_path()
            self.mode, self.url, self.error, self.log = mode, "", "", deque(maxlen=40)
            if not binary:
                self.status, self.error = "error", "cloudflared kurulu değil. Termux'ta: pkg install cloudflared"
                return self.snapshot()
            env = dict(os.environ)
            if mode == "quick":
                # "localhost" bazı telefonlarda önce IPv6 (::1) olarak çözülür; sunucu yalnızca IPv4 dinler.
                cmd = [binary, "tunnel", "--no-autoupdate", "--url", f"http://127.0.0.1:{self.port}"]
            elif mode == "named":
                if not token:
                    self.status, self.error = "error", "Adlandırılmış tünel için Cloudflare token'ı gerekli."
                    return self.snapshot()
                cmd = [binary, "tunnel", "--no-autoupdate", "run"]
                env["TUNNEL_TOKEN"] = token  # komut satırında görünmesin
                self._secret = token
                self.url = f"https://{hostname}" if hostname else ""
            else:
                self.status = "stopped"
                return self.snapshot()
            try:
                self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env,
                                             text=True, bufsize=1, start_new_session=True)
            except OSError as exc:
                self.status, self.error = "error", f"cloudflared başlatılamadı: {exc.strerror or exc}"
                return self.snapshot()
            self.status, self.started_at = "starting", time.time()
            threading.Thread(target=self._read, args=(self.proc,), daemon=True, name="tunnel-log").start()
            return self.snapshot()

    def _read(self, proc: subprocess.Popen):
        try:
            for line in proc.stdout:  # type: ignore[union-attr]
                self._handle(proc, line)
        except (ValueError, OSError):  # süreç kapatılırken akış kapandı
            pass
        code = proc.wait()
        if proc is self.proc and self.status != "stopped":
            self.status = "error"
            self.error = self.error or f"cloudflared durdu (çıkış kodu {code}). Son kayıtlara bak."

    def _handle(self, proc: subprocess.Popen, line: str):
        line = self._scrub(line.rstrip())
        if not line:
            return
        self.log.append(line)
        if proc is not self.proc:
            return
        m = QUICK_RE.search(line)
        if m and self.mode == "quick":
            self.url = m.group(0)
        if READY_RE.search(line) and (self.url or self.mode == "named"):
            self.status = "running"
            if self.error.startswith("Ağ QUIC"):
                self.error = ""
        low = line.lower()
        if ("failed to" in low or "error" in low) and self.status == "starting" and "lookup" in low:
            self.error = "DNS çözümlenemedi. Yönetim › Sistem ekranından DNS sunucusu seç (ör. OpenDNS) ve tekrar başlat."
        elif "failed to request quick tunnel" in low or "failed to unmarshal quick tunnel" in low:
            self.error = "Cloudflare hızlı tünel adresi veremedi (internet bağlantısı, DNS ya da Cloudflare tarafında geçici sorun). Birkaç dakika sonra tekrar dene."
        elif "unable to reach the origin service" in low or ("connection refused" in low and "origin" in low):
            self.error = f"Tünel açık ama uygulamaya ulaşamıyor (127.0.0.1:{self.port}). FotoTakip çalışıyor mu, port doğru mu?"
        elif "failed to dial to edge with quic" in low and not self.error:
            self.error = "Ağ QUIC (UDP) bağlantısına izin vermiyor; cloudflared HTTP/2'ye geçmeyi deniyor, biraz bekle."

    def _stop_locked(self):
        p, self.proc = self.proc, None
        self._secret = ""
        if p and p.poll() is None:
            p.terminate()
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
        if p and p.stdout:
            p.stdout.close()
        self.status, self.url = "stopped", ""

    def stop(self) -> dict:
        with self._lock:
            self._stop_locked()
            self.mode = "off"
            return self.snapshot()


# ---------- Termux DNS ----------

def resolv_path() -> str | None:
    """Termux'ta Go programları (cloudflared) DNS sunucusunu bu dosyadan okur."""
    if os.environ.get("FOTOTAKIP_RESOLV_CONF"):
        return os.environ["FOTOTAKIP_RESOLV_CONF"]
    prefix = os.environ.get("PREFIX", "")
    return os.path.join(prefix, "etc", "resolv.conf") if "com.termux" in prefix else None


def read_dns() -> dict:
    path = resolv_path()
    servers = []
    if path and os.path.exists(path):
        with open(path, encoding="utf-8", errors="replace") as f:
            servers = [ln.split()[1] for ln in f if ln.strip().startswith("nameserver") and len(ln.split()) > 1]
    preset = next((k for k, (_, ips) in DNS_PRESETS.items() if servers[:2] == ips), "custom" if servers else "system")
    return {"available": bool(path), "path": path, "servers": servers, "preset": preset,
            "presets": {k: {"name": n, "servers": ips} for k, (n, ips) in DNS_PRESETS.items()}}


def write_dns(preset: str) -> dict:
    path = resolv_path()
    if not path:
        raise ValueError("DNS ayarı yalnızca Termux'ta değiştirilebilir.")
    if preset not in DNS_PRESETS:
        raise ValueError("Bilinmeyen DNS seçimi.")
    name, ips = DNS_PRESETS[preset]
    if os.path.exists(path) and not os.path.exists(path + ".fototakip-yedek"):
        shutil.copy2(path, path + ".fototakip-yedek")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        f.write(f"# FotoTakip: {name}\n" + "".join(f"nameserver {ip}\n" for ip in ips))
    os.replace(path + ".tmp", path)
    return read_dns()
