"""Konum yardımcıları: uzaklık, ters geocoding (koordinat → adres) ve arka plan işçisi.

Adres servisi OpenStreetMap Nominatim'dir. Kullanım kuralları gereği:
  • saniyede en fazla 1 istek gönderilir,
  • uygulamayı tanıtan bir User-Agent kullanılır,
  • sonuçlar veritabanında önbelleğe alınır (aynı nokta ikinci kez sorulmaz).
Kapatmak için: FOTOTAKIP_GEOCODER=off. Başka bir uyumlu sunucu için: FOTOTAKIP_GEOCODER=https://…/reverse
Not: Açıkken fotoğraf koordinatları OpenStreetMap Vakfı'nın sunucusuna gönderilir.
"""

from __future__ import annotations

import json
import math
import queue
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from . import __version__, db

NOMINATIM = "https://nominatim.openstreetmap.org/reverse"
FAR_METERS = 500          # fotoğraf müşteri konumundan bu kadar uzaksa uyar
SAME_PLACE_METERS = 150   # adres önerisi için "farklı yer" eşiği


def distance_m(lat1, lng1, lat2, lng2) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def fmt_distance(m: float) -> str:
    return f"{m:.0f} m" if m < 1000 else f"{m / 1000:.1f} km".replace(".", ",")


def format_address(data: dict) -> str | None:
    """Nominatim yanıtını Türkiye'deki adres alışkanlığına yakın kısa bir metne çevirir."""
    a = data.get("address") or {}
    mah = a.get("neighbourhood") or a.get("suburb") or a.get("quarter")
    street = a.get("road") or a.get("pedestrian") or a.get("footway")
    if street and a.get("house_number"):
        street = f"{street} No {a['house_number']}"
    district = a.get("town") or a.get("city_district") or a.get("county") or a.get("district") or a.get("village")
    city = a.get("province") or a.get("city") or a.get("state")
    head = ", ".join(x for x in (mah, street) if x)
    tail = "/".join(x for x in (district, city) if x and x != head)
    text = ", ".join(x for x in (head, tail) if x)
    if not text:
        disp = data.get("display_name") or ""
        text = ", ".join(p.strip() for p in disp.split(",")[:4] if p.strip())
    return text or None


class Geocoder:
    def __init__(self, db_path: str, setting: str = "on", publish=None, contact: str = ""):
        self.db_path = db_path
        self.enabled = setting.lower() not in ("off", "0", "false", "kapali", "kapalı")
        self.endpoint = setting if setting.startswith("http") else NOMINATIM
        self.publish = publish or (lambda ev: None)
        ua = f"FotoTakip/{__version__} (self-hosted field service app)"
        self.user_agent = f"{ua} {contact}".strip()
        self._lock = threading.Lock()
        self._last = 0.0
        self._q: queue.Queue = queue.Queue()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._worker, name="geocoder", daemon=True)
        self._thread.start()

    # ---- tek istek ----
    @staticmethod
    def key(lat: float, lng: float) -> str:
        return f"{lat:.4f},{lng:.4f}"  # ~11 m hücre

    def reverse(self, con, lat: float, lng: float, timeout: float = 8.0) -> str | None:
        k = self.key(lat, lng)
        row = con.execute("SELECT address FROM geocode_cache WHERE key = ?", (k,)).fetchone()
        if row:
            return row["address"]
        if not self.enabled:
            return None
        with self._lock:  # saniyede en fazla 1 istek
            wait = 1.1 - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()
            qs = urllib.parse.urlencode({"format": "jsonv2", "lat": f"{lat:.6f}", "lon": f"{lng:.6f}",
                                         "zoom": 18, "addressdetails": 1, "accept-language": "tr"})
            req = urllib.request.Request(f"{self.endpoint}?{qs}", headers={"User-Agent": self.user_agent})
            try:
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    data = json.loads(r.read().decode("utf-8"))
            except (urllib.error.URLError, TimeoutError, ValueError, OSError):
                return None
        if not isinstance(data, dict) or data.get("error"):
            return None
        address = format_address(data)
        if address:
            with db.tx(con):
                con.execute("INSERT OR REPLACE INTO geocode_cache(key, address, raw, created_at) VALUES (?,?,?,?)",
                            (k, address, json.dumps(data, ensure_ascii=False)[:20000], db.now()))
        return address

    # ---- arka plan ----
    def enqueue(self, photo_id: str):
        self._q.put(photo_id)

    def stop(self):
        self._stop.set()
        self._q.put(None)

    def drain(self, timeout: float = 10.0) -> bool:
        """Testler için: kuyruk boşalana kadar bekle."""
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if self._q.unfinished_tasks == 0:
                return True
            time.sleep(0.05)
        return False

    def _worker(self):
        while not self._stop.is_set():
            pid = self._q.get()
            try:
                if pid:
                    self._process(pid)
            except Exception as exc:  # işçi asla ölmesin
                print(f"[geocoder] {pid}: {exc!r}")
            finally:
                self._q.task_done()

    def _process(self, photo_id: str):
        con = db.connect(self.db_path)
        try:
            ph = con.execute("SELECT id, lat, lng, gps_source, address FROM photos WHERE id = ?", (photo_id,)).fetchone()
            if not ph or ph["lat"] is None or ph["gps_source"] not in ("exif", "device"):
                return
            address = ph["address"] or self.reverse(con, ph["lat"], ph["lng"])
            if not address:
                return
            touched = set()
            with db.tx(con):
                con.execute("UPDATE photos SET address = ? WHERE id = ?", (address, photo_id))
                projects = con.execute(
                    "SELECT DISTINCT p.* FROM projects p JOIN tasks t ON t.project_id = p.id "
                    "JOIN task_photos tp ON tp.task_id = t.id WHERE tp.photo_id = ?", (photo_id,)).fetchall()
                for p in projects:
                    near = p["lat"] is None or distance_m(p["lat"], p["lng"], ph["lat"], ph["lng"]) <= SAME_PLACE_METERS * 2
                    if not p["address"] and near:
                        con.execute("UPDATE projects SET address = ?, address_source = 'photo', suggested_address = NULL WHERE id = ?",
                                    (address, p["id"]))
                        touched.add(p["id"])
                    elif p["address"] != address and p["address_source"] != "photo" and near and not p["suggested_address"]:
                        con.execute("UPDATE projects SET suggested_address = ? WHERE id = ?", (address, p["id"]))
                        touched.add(p["id"])
            self.publish({"type": "geocode", "photo": photo_id, "projects": sorted(touched), "by": None})
        finally:
            con.close()
