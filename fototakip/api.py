"""API uç noktaları. Her fonksiyon (req) alır, dict döner ya da ApiError fırlatır."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import shutil
import sqlite3
import tempfile
import threading
import time
import zipfile
from datetime import date, datetime, timedelta

from . import __version__, ai_review, auth, db, geo, images, secrets, tunnel

STATUSES = ("open", "progress", "review", "done")
STATUS_NAMES = {"open": "Açık", "progress": "Devam ediyor", "review": "Onay bekliyor", "done": "Tamamlandı"}
TYPES = {"before": "önce", "progress": "süreç", "after": "sonra", "issue": "sorun"}
ROUTES: list[tuple[str, re.Pattern, object, bool]] = []


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, extra: dict | None = None):
        super().__init__(message)
        self.status, self.code, self.message, self.extra = status, code, message, extra or {}


def route(method: str, pattern: str, auth_required: bool = True):
    def deco(fn):
        ROUTES.append((method, re.compile("^" + pattern + "$"), fn, auth_required))
        return fn
    return deco


# ---------- yardımcılar ----------

def wo(no: int) -> str:
    return f"İE-{no:04d}"


def need_manager(req):
    if req.user["role"] != "manager":
        raise ApiError(403, "forbidden", "Bu işlem için yönetici yetkisi gerekiyor.")


def text_field(body: dict, key: str, required=True, max_len=500) -> str:
    v = body.get(key)
    if v is None or (isinstance(v, str) and not v.strip()):
        if required:
            raise ApiError(400, "missing_field", f"'{key}' alanı gerekli.")
        return ""
    if not isinstance(v, str):
        raise ApiError(400, "bad_field", f"'{key}' metin olmalı.")
    v = v.strip()
    if len(v) > max_len:
        raise ApiError(400, "too_long", f"'{key}' en fazla {max_len} karakter olabilir.")
    return v


def get_task(req, task_id: str, for_write=False):
    t = req.con.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not t or not can_see(req.user, t):
        raise ApiError(404, "not_found", "İş bulunamadı.")
    if for_write and req.user["role"] != "manager" and t["assignee_id"] not in (req.user["id"],):
        raise ApiError(403, "forbidden", "Bu iş sana atanmamış. Önce işi üstlen.")
    return t


def can_see(user, t) -> bool:
    return user["role"] == "manager" or t["assignee_id"] in (None, user["id"])


def log(con, task_id: str, by: str, text: str):
    con.execute("INSERT INTO activity(task_id, by_id, text, created_at) VALUES (?, ?, ?, ?)",
                (task_id, by, text, db.now()))


def touch(con, task_id: str):
    con.execute("UPDATE tasks SET updated_at = ?, version = version + 1 WHERE id = ?", (db.now(), task_id))


def valid_date(s) -> str:
    try:
        return date.fromisoformat(str(s)).isoformat()
    except ValueError:
        raise ApiError(400, "bad_date", "Tarih YYYY-AA-GG biçiminde olmalı.")


def user_name(con, uid: str | None) -> str:
    if not uid:
        return "Atanmamış"
    r = con.execute("SELECT name FROM users WHERE id = ?", (uid,)).fetchone()
    return r["name"] if r else "?"


def run_automation(con, task_id: str) -> dict:
    """'Sonra' fotoğrafı geldiğinde işi onaya taşır; koşul tutmazsa nedenini söyler."""
    t = con.execute("SELECT status FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if db.setting(con, "auto_rule", "1") != "1" or t["status"] not in ("open", "progress"):
        return {"moved": False, "message": None}
    has_before = con.execute(
        "SELECT 1 FROM task_photos WHERE task_id = ? AND type = 'before' LIMIT 1", (task_id,)).fetchone()
    if not has_before:
        return {"moved": False, "message": "Önce fotoğrafı olmadığı için iş onaya taşınmadı."}
    missing = con.execute(
        "SELECT COUNT(*) FROM checklist WHERE task_id = ? AND require_proof = 1 AND (done = 0 OR proof_photo_id IS NULL)",
        (task_id,)).fetchone()[0]
    if missing:
        return {"moved": False, "message": f"{missing} zorunlu kontrol maddesi kanıtsız; iş onaya taşınmadı."}
    con.execute("UPDATE tasks SET status = 'review', rejected_reason = NULL WHERE id = ?", (task_id,))
    log(con, task_id, "sys", "Otomasyon: “Onay bekliyor”a taşındı")
    return {"moved": True, "message": "Otomasyon: iş “Onay bekliyor”a taşındı."}


# ---------- sağlık ve oturum ----------

@route("GET", "/api/health", auth_required=False)
def health(req):
    return {"status": "ok", "version": __version__, "needs_setup": needs_setup(req.con),
            "pillow": images.HAVE_PIL}


# ---------- ilk kurulum ----------
# Boş veritabanında kimse giriş yapamaz. Sunucu başlarken Termux ekranına (ve veri klasöründeki
# kurulum-kodu.txt dosyasına) tek kullanımlık bir kod yazar; ilk yönetici bu kodla açılır.
# Kod veritabanında yalnızca özet (SHA-256) olarak durur; 5 hatalı denemede geçersiz olur.
SETUP_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
SETUP_MAX_FAILS = 5


def needs_setup(con) -> bool:
    return con.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0


def _code_hash(code: str) -> str:
    return hashlib.sha256(code.strip().upper().replace("-", "").replace(" ", "").encode()).hexdigest()


def new_setup_code(con) -> str:
    import secrets as _rnd
    raw = "".join(_rnd.choice(SETUP_ALPHABET) for _ in range(8))
    with db.tx(con):
        db.set_setting(con, "setup_code", _code_hash(raw))
        db.set_setting(con, "setup_fails", "0")
    return raw[:4] + "-" + raw[4:]


def setup_code_file(cfg) -> str:
    return os.path.join(cfg.data_dir, "kurulum-kodu.txt")


@route("POST", "/api/setup", auth_required=False)
def first_setup(req):
    con = req.con
    if not needs_setup(con):
        raise ApiError(409, "already_setup", "Kurulum zaten yapılmış. Giriş ekranını kullan.")
    body = req.json()
    stored = db.setting(con, "setup_code", "")
    fails = int(db.setting(con, "setup_fails", "0") or 0)
    if not stored or fails >= SETUP_MAX_FAILS:
        raise ApiError(423, "setup_locked", "Kurulum kodu geçersiz oldu. Termux'ta FotoTakip'i yeniden başlat; yeni kod ekrana yazılır.")
    if not hmac.compare_digest(_code_hash(str(body.get("code") or "")), stored):
        with db.tx(con):
            db.set_setting(con, "setup_fails", str(fails + 1))
        left = SETUP_MAX_FAILS - fails - 1
        raise ApiError(403, "bad_setup_code", f"Kurulum kodu hatalı. Kalan deneme: {left}." if left else
                       "Kurulum kodu hatalı ve artık geçersiz. FotoTakip'i yeniden başlat.")
    name = text_field(body, "name", max_len=80)
    username = text_field(body, "username", max_len=32).lower()
    if not re.fullmatch(r"[a-z0-9._-]{3,32}", username):
        raise ApiError(400, "bad_username", "Kullanıcı adı 3-32 karakter: küçük harf, rakam, nokta, tire.")
    password = body.get("password") or ""
    if len(password) < 8:
        raise ApiError(400, "weak_password", "Yönetici parolası en az 8 karakter olmalı.")
    if password.lower() in (DEMO_PASSWORD, username, "12345678", "password", "parola123"):
        raise ApiError(400, "weak_password", "Bu parola kolay tahmin edilir; başka bir parola seç.")
    uid = db.new_id()
    with db.tx(con):
        if not needs_setup(con):  # aynı anda iki kurulum isteği
            raise ApiError(409, "already_setup", "Kurulum zaten yapılmış.")
        con.execute("INSERT INTO users(id, username, name, short, role, pw_hash, created_at) VALUES (?,?,?,?,?,?,?)",
                    (uid, username, name, auth.initials(name), "manager", auth.hash_password(password), db.now()))
        con.execute("DELETE FROM settings WHERE key IN ('setup_code', 'setup_fails')")
    try:
        os.remove(setup_code_file(req.cfg))
    except OSError:
        pass
    token = auth.create_session(con, uid)
    req.set_cookie = token
    req.publish({"type": "users"})
    row = con.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
    return {"token": token, "user": {k: row[k] for k in ("id", "username", "name", "short", "role")}}


# İnternete açıldığında parola denemesini yavaşlatır: kullanıcı başına 10 dakikada 5 hatalı deneme.
MAX_FAILS, LOCK_SECONDS = 5, 600
_FAILS: dict[str, list[float]] = {}
_FAIL_LOCK = threading.Lock()


@route("POST", "/api/login", auth_required=False)
def login(req):
    body = req.json()
    username = text_field(body, "username", max_len=64)
    password = body.get("password") or ""
    key = username.lower()
    now = time.monotonic()
    with _FAIL_LOCK:
        recent = [t for t in _FAILS.get(key, []) if now - t < LOCK_SECONDS]
        _FAILS[key] = recent
    if len(recent) >= MAX_FAILS:
        wait = int(LOCK_SECONDS - (now - recent[0])) // 60 + 1
        raise ApiError(429, "too_many_attempts", f"Çok fazla hatalı deneme. {wait} dakika sonra tekrar dene.")
    row = req.con.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if not row or not auth.verify_password(password, row["pw_hash"]):
        with _FAIL_LOCK:
            _FAILS.setdefault(key, []).append(now)
        raise ApiError(401, "bad_credentials", "Kullanıcı adı veya parola hatalı.")
    with _FAIL_LOCK:
        _FAILS.pop(key, None)
    token = auth.create_session(req.con, row["id"])
    req.set_cookie = token
    return {"token": token, "user": {k: row[k] for k in ("id", "username", "name", "short", "role")}}


@route("POST", "/api/logout")
def logout(req):
    auth.delete_session(req.con, req.token)
    req.set_cookie = ""
    return {"ok": True}


@route("PATCH", "/api/me/password")
def change_password(req):
    body = req.json()
    row = req.con.execute("SELECT pw_hash FROM users WHERE id = ?", (req.user["id"],)).fetchone()
    if not auth.verify_password(body.get("old") or "", row["pw_hash"]):
        raise ApiError(400, "bad_credentials", "Mevcut parola hatalı.")
    new = body.get("new") or ""
    if len(new) < 6:
        raise ApiError(400, "weak_password", "Yeni parola en az 6 karakter olmalı.")
    with db.tx(req.con):
        req.con.execute("UPDATE users SET pw_hash = ? WHERE id = ?", (auth.hash_password(new), req.user["id"]))
        req.con.execute("DELETE FROM sessions WHERE user_id = ? AND token != ?", (req.user["id"], req.token))
    return {"ok": True}


# ---------- toplu veri ----------

@route("GET", "/api/bootstrap")
def bootstrap(req):
    con, user = req.con, req.user
    users = [dict(r) for r in con.execute("SELECT id, username, name, short, role FROM users ORDER BY role, name")]
    projects = [dict(r) for r in con.execute("SELECT * FROM projects ORDER BY created_at")]
    if user["role"] == "manager":
        rows = con.execute("SELECT * FROM tasks ORDER BY no").fetchall()
    else:
        rows = con.execute("SELECT * FROM tasks WHERE assignee_id IS NULL OR assignee_id = ? ORDER BY no",
                           (user["id"],)).fetchall()
    tasks = {r["id"]: {**dict(r), "no_label": wo(r["no"]), "photos": [], "comments": [], "checklist": [],
                       "activity": [], "signature": None} for r in rows}
    ids = list(tasks)
    photos: dict = {}
    if ids:
        marks = ",".join("?" * len(ids))
        for r in con.execute(f"SELECT * FROM task_photos WHERE task_id IN ({marks}) ORDER BY created_at", ids):
            tasks[r["task_id"]]["photos"].append({"pid": r["photo_id"], "type": r["type"]})
            photos[r["photo_id"]] = None
        for r in con.execute(f"SELECT * FROM comments WHERE task_id IN ({marks}) ORDER BY created_at", ids):
            tasks[r["task_id"]]["comments"].append({"id": r["id"], "by": r["by_id"], "text": r["text"], "at": r["created_at"]})
        for r in con.execute(f"SELECT * FROM checklist WHERE task_id IN ({marks}) ORDER BY sort, rowid", ids):
            tasks[r["task_id"]]["checklist"].append({"id": r["id"], "text": r["text"], "done": bool(r["done"]),
                                                     "require_proof": bool(r["require_proof"]), "proof": r["proof_photo_id"]})
            if r["proof_photo_id"]:
                photos[r["proof_photo_id"]] = None
        for r in con.execute(f"SELECT * FROM activity WHERE task_id IN ({marks}) ORDER BY id", ids):
            tasks[r["task_id"]]["activity"].append({"by": r["by_id"], "text": r["text"], "at": r["created_at"]})
        for r in con.execute(f"SELECT task_id, signer, created_at FROM signatures WHERE task_id IN ({marks})", ids):
            tasks[r["task_id"]]["signature"] = {"signer": r["signer"], "at": r["created_at"]}
    if photos:
        pids = list(photos)
        marks = ",".join("?" * len(pids))
        for r in con.execute(f"SELECT id, mime, width, height, taken_at, lat, lng, gps_source, gps_accuracy, address, uploaded_by FROM photos WHERE id IN ({marks})", pids):
            photos[r["id"]] = {**dict(r), "annotations": []}
        for r in con.execute(f"SELECT * FROM annotations WHERE photo_id IN ({marks}) ORDER BY created_at", pids):
            photos[r["photo_id"]]["annotations"].append({"id": r["id"], "x": r["x"], "y": r["y"], "text": r["text"], "by": r["by_id"]})
        for r in con.execute(f"SELECT * FROM ai_reviews WHERE photo_id IN ({marks})", pids):
            photos[r["photo_id"]]["ai"] = {**json.loads(r["result"]), "by": r["by_id"], "at": r["created_at"]}
    return {"me": user, "users": users, "projects": projects, "tasks": list(tasks.values()), "photos": photos,
            "settings": {"auto_rule": db.setting(con, "auto_rule", "1") == "1",
                         "ai_enabled": db.setting(con, "ai_enabled", "0") == "1"},
            "server_time": db.now(), "version": __version__}


@route("GET", "/api/search")
def search(req):
    q = (req.query.get("q") or "").strip()
    if len(q) < 2:
        return {"ids": []}
    like = f"%{q}%"
    rows = req.con.execute(
        """SELECT DISTINCT t.id, t.assignee_id FROM tasks t
           LEFT JOIN comments c ON c.task_id = t.id
           LEFT JOIN task_photos tp ON tp.task_id = t.id
           LEFT JOIN annotations a ON a.photo_id = tp.photo_id
           WHERE t.title LIKE ? OR ('İE-' || printf('%04d', t.no)) LIKE ? OR c.text LIKE ? OR a.text LIKE ?""",
        (like, like, like, like)).fetchall()
    return {"ids": [r["id"] for r in rows if can_see(req.user, r)]}


# ---------- kullanıcılar ve projeler ----------

@route("POST", "/api/users")
def create_user(req):
    need_manager(req)
    body = req.json()
    username = text_field(body, "username", max_len=32).lower()
    if not re.fullmatch(r"[a-z0-9._-]{3,32}", username):
        raise ApiError(400, "bad_username", "Kullanıcı adı 3-32 karakter: küçük harf, rakam, nokta, tire.")
    name = text_field(body, "name", max_len=80)
    role = body.get("role", "field")
    if role not in ("manager", "field"):
        raise ApiError(400, "bad_role", "Rol 'manager' veya 'field' olmalı.")
    password = body.get("password") or ""
    if len(password) < 6:
        raise ApiError(400, "weak_password", "Parola en az 6 karakter olmalı.")
    uid = db.new_id()
    try:
        with db.tx(req.con):
            req.con.execute("INSERT INTO users(id, username, name, short, role, pw_hash, created_at) VALUES (?,?,?,?,?,?,?)",
                            (uid, username, name, auth.initials(name), role, auth.hash_password(password), db.now()))
    except sqlite3.IntegrityError:
        raise ApiError(409, "username_taken", "Bu kullanıcı adı kullanılıyor.")
    req.publish({"type": "users"})
    return {"id": uid}


@route("POST", "/api/projects")
def create_project(req):
    need_manager(req)
    body = req.json()
    name = text_field(body, "name", max_len=120)
    short = text_field(body, "short", required=False, max_len=40) or name.split("·")[0].strip()[:40]
    lat, lng = body.get("lat"), body.get("lng")
    try:
        lat = float(lat) if lat not in (None, "") else None
        lng = float(lng) if lng not in (None, "") else None
    except (TypeError, ValueError):
        raise ApiError(400, "bad_gps", "Enlem ve boylam sayı olmalı.")
    if (lat is not None and not -90 <= lat <= 90) or (lng is not None and not -180 <= lng <= 180):
        raise ApiError(400, "bad_gps", "Enlem -90..90, boylam -180..180 aralığında olmalı.")
    pid = db.new_id()
    address = text_field(body, "address", False, 200)
    loc_src = body.get("location_source") if body.get("location_source") in ("manual", "device", "map", "photo") else "manual"
    addr_src = body.get("address_source") if body.get("address_source") in ("manual", "geocode") else "manual"
    with db.tx(req.con):
        req.con.execute("""INSERT INTO projects(id, name, short, client, contact, address, lat, lng, created_at,
                           address_source, location_source) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                        (pid, name, short, text_field(body, "client", False, 120), text_field(body, "contact", False, 120),
                         address, lat, lng, db.now(), addr_src if address else "none", loc_src if lat is not None else "none"))
    req.publish({"type": "projects"})
    return {"id": pid}


def _coords(body):
    lat, lng = body.get("lat"), body.get("lng")
    try:
        lat = float(lat) if lat not in (None, "") else None
        lng = float(lng) if lng not in (None, "") else None
    except (TypeError, ValueError):
        raise ApiError(400, "bad_gps", "Enlem ve boylam sayı olmalı.")
    if (lat is None) != (lng is None):
        raise ApiError(400, "bad_gps", "Enlem ve boylam birlikte girilmeli.")
    if lat is not None and not (-90 <= lat <= 90 and -180 <= lng <= 180):
        raise ApiError(400, "bad_gps", "Enlem -90..90, boylam -180..180 aralığında olmalı.")
    return lat, lng


@route("PATCH", r"/api/projects/(?P<pid>\w+)")
def update_project(req):
    need_manager(req)
    body = req.json()
    with db.tx(req.con):
        p = req.con.execute("SELECT * FROM projects WHERE id = ?", (req.match["pid"],)).fetchone()
        if not p:
            raise ApiError(404, "not_found", "Müşteri bulunamadı.")
        sets = {}
        for key, n in (("name", 120), ("short", 40), ("client", 120), ("contact", 120)):
            if key in body:
                sets[key] = text_field(body, key, required=key == "name", max_len=n)
        if "address" in body:
            sets["address"] = text_field(body, "address", False, 200)
            sets["address_source"] = "manual" if sets["address"] else "none"
            sets["suggested_address"] = None
        if body.get("apply_suggestion"):
            if not p["suggested_address"]:
                raise ApiError(409, "no_suggestion", "Uygulanacak adres önerisi yok.")
            sets.update(address=p["suggested_address"], address_source="photo", suggested_address=None)
        if body.get("dismiss_suggestion"):
            sets["suggested_address"] = None
        if "lat" in body or "lng" in body:
            lat, lng = _coords(body)
            src = body.get("location_source") if body.get("location_source") in ("manual", "device", "map", "photo") else "manual"
            sets.update(lat=lat, lng=lng, location_source=src if lat is not None else "none")
        if sets:
            cols = ", ".join(f"{k} = ?" for k in sets)
            req.con.execute(f"UPDATE projects SET {cols} WHERE id = ?", (*sets.values(), p["id"]))
    req.publish({"type": "projects"})
    return {"ok": True}


@route("GET", "/api/geocode")
def geocode(req):
    try:
        lat, lng = float(req.query.get("lat", "")), float(req.query.get("lng", ""))
    except ValueError:
        raise ApiError(400, "bad_gps", "lat ve lng gerekli.")
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        raise ApiError(400, "bad_gps", "Koordinat aralık dışında.")
    if not req.geo.enabled:
        row = req.con.execute("SELECT address FROM geocode_cache WHERE key = ?", (req.geo.key(lat, lng),)).fetchone()
        if not row:
            raise ApiError(503, "geocoder_off", "Adres bulma kapalı. Adresi elle yaz.")
    address = req.geo.reverse(req.con, lat, lng)
    if not address:
        raise ApiError(503, "geocoder_unreachable", "Adres bulunamadı: adres servisine ulaşılamadı veya bu noktada adres yok. Elle yazabilirsin.")
    return {"address": address}


@route("PATCH", "/api/settings")
def update_settings(req):
    need_manager(req)
    body = req.json()
    with db.tx(req.con):
        if "auto_rule" in body:
            db.set_setting(req.con, "auto_rule", "1" if body["auto_rule"] else "0")
    req.publish({"type": "settings"})
    return {"ok": True}


# ---------- işler ----------

def insert_task(con, user, project_id: str, title: str, due: str | None = None, priority="normal",
                assignee_id: str | None = "self") -> dict:
    if not con.execute("SELECT 1 FROM projects WHERE id = ?", (project_id,)).fetchone():
        raise ApiError(400, "bad_project", "Proje bulunamadı.")
    no = db.next_task_no(con)
    untitled = 0
    if not title:
        title = f"Başlıksız iş · {datetime.now().strftime('%H:%M')}"
        untitled = 1
    if assignee_id == "self":
        assignee_id = None if user["role"] == "manager" else user["id"]
    tid = db.new_id()
    ts = db.now()
    con.execute("""INSERT INTO tasks(id, no, project_id, title, untitled, status, assignee_id, due, priority,
                   created_by, created_at, updated_at) VALUES (?,?,?,?,?, 'open', ?,?,?,?,?,?)""",
                (tid, no, project_id, title, untitled, assignee_id, due or (date.today() + timedelta(days=3)).isoformat(),
                 priority, user["id"], ts, ts))
    return {"id": tid, "no": no}


@route("POST", "/api/tasks")
def create_task(req):
    body = req.json()
    priority = body.get("priority", "normal")
    if priority not in ("normal", "high"):
        raise ApiError(400, "bad_priority", "Öncelik 'normal' veya 'high' olmalı.")
    due = valid_date(body["due"]) if body.get("due") else None
    assignee = body.get("assignee_id", "self")
    if assignee not in ("self", None) and req.user["role"] != "manager":
        raise ApiError(403, "forbidden", "Atamayı yalnızca yönetici yapabilir.")
    with db.tx(req.con):
        t = insert_task(req.con, req.user, body.get("project_id"), text_field(body, "title", False, 160), due, priority, assignee)
        log(req.con, t["id"], req.user["id"], "İşi oluşturdu")
    req.publish({"type": "task", "id": t["id"]})
    return {"id": t["id"], "no_label": wo(t["no"])}


@route("PATCH", r"/api/tasks/(?P<tid>\w+)")
def update_task(req):
    body = req.json()
    con, user = req.con, req.user
    with db.tx(con):
        t = get_task(req, req.match["tid"], for_write=True)
        if "version" in body and body["version"] != t["version"]:
            raise ApiError(409, "conflict", "Bu iş sen bakarken başka biri tarafından değiştirildi. Güncel hali yüklendi; değişikliğini tekrar yap.")
        msgs = []
        if "title" in body:
            title = text_field(body, "title", max_len=160)
            if title != t["title"]:
                con.execute("UPDATE tasks SET title = ?, untitled = 0 WHERE id = ?", (title, t["id"]))
                msgs.append("Başlığı değiştirdi")
        if "due" in body:
            due = valid_date(body["due"])
            if due != t["due"]:
                con.execute("UPDATE tasks SET due = ? WHERE id = ?", (due, t["id"]))
                msgs.append(f"Son tarihi {due} yaptı")
        if "priority" in body:
            if body["priority"] not in ("normal", "high"):
                raise ApiError(400, "bad_priority", "Öncelik 'normal' veya 'high' olmalı.")
            con.execute("UPDATE tasks SET priority = ? WHERE id = ?", (body["priority"], t["id"]))
            msgs.append("Önceliği " + ("acil" if body["priority"] == "high" else "normal") + " yaptı")
        if "assignee_id" in body:
            need_manager(req)
            a = body["assignee_id"] or None
            if a and not con.execute("SELECT 1 FROM users WHERE id = ?", (a,)).fetchone():
                raise ApiError(400, "bad_user", "Kullanıcı bulunamadı.")
            if a != t["assignee_id"]:
                con.execute("UPDATE tasks SET assignee_id = ? WHERE id = ?", (a, t["id"]))
                msgs.append(f"{user_name(con, a)} kişisine atadı" if a else "Atamayı kaldırdı")
        if "status" in body:
            s = body["status"]
            if s not in STATUSES:
                raise ApiError(400, "bad_status", "Geçersiz durum.")
            if s != t["status"]:
                if user["role"] != "manager":
                    if s == "done":
                        raise ApiError(403, "forbidden", "“Tamamlandı” durumuna yalnızca yönetici taşıyabilir. İşi “Onay bekliyor”a taşı.")
                    if t["status"] == "done":
                        raise ApiError(403, "forbidden", "Tamamlanmış işi yalnızca yönetici yeniden açabilir.")
                rejected = t["rejected_reason"] if s == "progress" else None
                con.execute("UPDATE tasks SET status = ?, rejected_reason = ? WHERE id = ?", (s, rejected, t["id"]))
                msgs.append(f"Durumu “{STATUS_NAMES[s]}” yaptı")
        for m in msgs:
            log(con, t["id"], user["id"], m)
        if msgs:
            touch(con, t["id"])
    req.publish({"type": "task", "id": t["id"]})
    return {"ok": True}


@route("POST", r"/api/tasks/(?P<tid>\w+)/claim")
def claim_task(req):
    with db.tx(req.con):
        t = get_task(req, req.match["tid"])
        if t["assignee_id"]:
            raise ApiError(409, "already_assigned", f"Bu iş zaten {user_name(req.con, t['assignee_id'])} kişisine atanmış.")
        req.con.execute("UPDATE tasks SET assignee_id = ? WHERE id = ?", (req.user["id"], t["id"]))
        log(req.con, t["id"], req.user["id"], "İşi üstlendi")
        touch(req.con, t["id"])
    req.publish({"type": "task", "id": t["id"]})
    return {"ok": True}


@route("POST", r"/api/tasks/(?P<tid>\w+)/review")
def review_task(req):
    need_manager(req)
    body = req.json()
    decision = body.get("decision")
    with db.tx(req.con):
        t = get_task(req, req.match["tid"])
        if t["status"] != "review":
            raise ApiError(409, "not_in_review", "Yalnızca “Onay bekliyor” durumundaki iş onaylanabilir.")
        if decision == "approve":
            req.con.execute("UPDATE tasks SET status = 'done', rejected_reason = NULL WHERE id = ?", (t["id"],))
            log(req.con, t["id"], req.user["id"], "Onayladı")
        elif decision == "reject":
            reason = text_field(body, "reason", max_len=300)
            req.con.execute("UPDATE tasks SET status = 'progress', rejected_reason = ? WHERE id = ?", (reason, t["id"]))
            req.con.execute("INSERT INTO comments(id, task_id, by_id, text, created_at) VALUES (?,?,?,?,?)",
                            (db.new_id(), t["id"], req.user["id"], f"Geri gönderildi: {reason}", db.now()))
            log(req.con, t["id"], req.user["id"], f"Geri gönderdi: {reason}")
        else:
            raise ApiError(400, "bad_decision", "Karar 'approve' veya 'reject' olmalı.")
        touch(req.con, t["id"])
    req.publish({"type": "task", "id": t["id"]})
    return {"ok": True}


@route("DELETE", r"/api/tasks/(?P<tid>\w+)")
def delete_task(req):
    need_manager(req)
    with db.tx(req.con):
        t = get_task(req, req.match["tid"])
        req.con.execute("UPDATE checklist SET proof_photo_id = NULL WHERE task_id = ?", (t["id"],))
        req.con.execute("DELETE FROM tasks WHERE id = ?", (t["id"],))
    req.publish({"type": "task", "id": t["id"]})
    return {"ok": True}


# ---------- fotoğraflar ----------

@route("POST", "/api/photos")
def upload_photo(req):
    """Gövde = ham fotoğraf baytları. Parametreler sorgu dizesinde.

    type=before|progress|after|issue, task_id=... ya da new_task=1&project_id=...&title=...
    lat/lng: cihaz konumu (EXIF'te konum yoksa kullanılır).
    """
    q, con, user = req.query, req.con, req.user
    ptype = q.get("type", "issue")
    if ptype not in TYPES:
        raise ApiError(400, "bad_type", "Fotoğraf türü before, progress, after veya issue olmalı.")
    data = req.body(limit=req.cfg.max_upload_mb * 1024 * 1024)
    if not data:
        raise ApiError(400, "empty_body", "Fotoğraf verisi boş.")
    digest = hashlib.sha256(data).hexdigest()

    device = None
    try:
        if q.get("lat") and q.get("lng"):
            lat, lng = float(q["lat"]), float(q["lng"])
            acc = float(q["acc"]) if q.get("acc") else None
            if -90 <= lat <= 90 and -180 <= lng <= 180:
                device = (lat, lng, acc)
    except ValueError:
        device = None

    existing = con.execute("SELECT id FROM photos WHERE sha256 = ?", (digest,)).fetchone()
    meta, photo_id = None, None
    if not existing:
        photo_id = db.new_id()
        try:
            meta = images.store(data, os.path.join(req.cfg.data_dir, "photos"), photo_id)
        except images.ImageError as e:
            raise ApiError(415, e.code, e.message)

    try:
        result = _link_photo(req, q, ptype, digest, existing, meta, device, photo_id)
    except BaseException:
        if meta:  # kaydedilen ama veritabanına girmeyen dosyaları temizle
            for name in {meta["path"], meta["thumb_path"]}:
                try:
                    os.remove(os.path.join(req.cfg.data_dir, "photos", name))
                except OSError:
                    pass
        raise
    req.publish({"type": "task", "id": result["task_id"]})
    if result.pop("_geocode", False):
        req.geo.enqueue(result["photo_id"])
    return result


def _link_photo(req, q, ptype, digest, existing, meta, device, photo_id):
    con, user = req.con, req.user
    with db.tx(con):
        if q.get("new_task") == "1":
            t = insert_task(con, user, q.get("project_id"), (q.get("title") or "").strip()[:160])
            task_id = t["id"]
            log(con, task_id, user["id"], "Fotoğraftan iş oluşturdu" + ("" if q.get("title") else " (başlık girilmedi)"))
        else:
            task_id = get_task(req, q.get("task_id", ""), for_write=True)["id"]
        trow = con.execute("SELECT project_id FROM tasks WHERE id = ?", (task_id,)).fetchone()
        prow = con.execute("SELECT * FROM projects WHERE id = ?", (trow["project_id"],)).fetchone()
        warning, geocode = None, False

        duplicate = False
        if existing:
            photo_id = existing["id"]
            duplicate = bool(con.execute("SELECT 1 FROM task_photos WHERE task_id = ? AND photo_id = ?",
                                         (task_id, photo_id)).fetchone())
        else:
            lat, lng, src, acc = meta.get("lat"), meta.get("lng"), "exif", None
            if lat is None and device:
                lat, lng, acc, src = device[0], device[1], device[2], "device"
            if lat is None:
                if prow["lat"] is not None:
                    lat, lng, src = prow["lat"], prow["lng"], "project"
                else:
                    src = "none"
            con.execute("""INSERT INTO photos(id, sha256, path, thumb_path, mime, width, height, taken_at, lat, lng,
                           gps_source, gps_accuracy, uploaded_by, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (photo_id, digest, meta["path"], meta["thumb_path"], meta["mime"], meta["width"], meta["height"],
                         meta.get("taken_at") or db.now(), lat, lng, src, acc, user["id"], db.now()))
            if src in ("exif", "device"):
                geocode = True
                if prow["lat"] is None:
                    # müşterinin konumu yoksa ilk konumlu fotoğraf müşterinin konumu olur
                    con.execute("UPDATE projects SET lat = ?, lng = ?, location_source = 'photo' WHERE id = ?",
                                (round(lat, 6), round(lng, 6), prow["id"]))
                    log(con, task_id, user["id"], f"Müşteri konumu bu fotoğraftan alındı ({prow['short']})")
                else:
                    d = geo.distance_m(prow["lat"], prow["lng"], lat, lng)
                    if d > geo.FAR_METERS:
                        warning = f"Fotoğraf {prow['short']} konumundan {geo.fmt_distance(d)} uzakta çekilmiş. Doğru müşteriyi mi seçtin?"
                        log(con, task_id, user["id"], f"Uyarı: fotoğraf müşteri konumundan {geo.fmt_distance(d)} uzakta")
        automation = {"moved": False, "message": None}
        if not duplicate:
            con.execute("INSERT INTO task_photos(task_id, photo_id, type, created_at) VALUES (?,?,?,?)",
                        (task_id, photo_id, ptype, db.now()))
            log(con, task_id, user["id"], f"{TYPES[ptype].capitalize()} fotoğrafı ekledi")
            if ptype == "after":
                automation = run_automation(con, task_id)
            touch(con, task_id)
    no = con.execute("SELECT no FROM tasks WHERE id = ?", (task_id,)).fetchone()["no"]
    return {"task_id": task_id, "no_label": wo(no), "photo_id": photo_id, "duplicate": duplicate,
            "already_stored": bool(existing), "automation": automation, "warning": warning, "_geocode": geocode}


@route("DELETE", r"/api/tasks/(?P<tid>\w+)/photos/(?P<pid>\w+)")
def unlink_photo(req):
    with db.tx(req.con):
        t = get_task(req, req.match["tid"], for_write=True)
        req.con.execute("UPDATE checklist SET proof_photo_id = NULL, done = CASE WHEN require_proof = 1 THEN 0 ELSE done END "
                        "WHERE task_id = ? AND proof_photo_id = ?", (t["id"], req.match["pid"]))
        cur = req.con.execute("DELETE FROM task_photos WHERE task_id = ? AND photo_id = ?", (t["id"], req.match["pid"]))
        if cur.rowcount:
            log(req.con, t["id"], req.user["id"], "Bir fotoğrafı işten kaldırdı")
            touch(req.con, t["id"])
    req.publish({"type": "task", "id": t["id"]})
    return {"ok": True}


def photo_visible(req, pid: str) -> bool:
    if req.user["role"] == "manager":
        return True
    row = req.con.execute(
        """SELECT 1 FROM task_photos tp JOIN tasks t ON t.id = tp.task_id
           WHERE tp.photo_id = ? AND (t.assignee_id IS NULL OR t.assignee_id = ?) LIMIT 1""",
        (pid, req.user["id"])).fetchone()
    if row:
        return True
    return bool(req.con.execute("SELECT 1 FROM photos WHERE id = ? AND uploaded_by = ?", (pid, req.user["id"])).fetchone())


@route("GET", r"/files/(?P<pid>\w+)")
def photo_file(req):
    pid = req.match["pid"]
    row = req.con.execute("SELECT * FROM photos WHERE id = ?", (pid,)).fetchone()
    if not row or not photo_visible(req, pid):
        raise ApiError(404, "not_found", "Fotoğraf bulunamadı.")
    name = row["thumb_path"] if req.query.get("s") == "t" else row["path"]
    return req.file(os.path.join(req.cfg.data_dir, "photos", name), row["mime"], immutable=True)


@route("POST", r"/api/photos/(?P<pid>\w+)/annotations")
def add_annotation(req):
    body = req.json()
    try:
        x, y = float(body.get("x")), float(body.get("y"))
    except (TypeError, ValueError):
        raise ApiError(400, "bad_point", "x ve y sayı olmalı.")
    if not (0 <= x <= 100 and 0 <= y <= 100):
        raise ApiError(400, "bad_point", "x ve y 0-100 arasında olmalı.")
    text = text_field(body, "text", max_len=300)
    with db.tx(req.con):
        t = get_task(req, body.get("task_id", ""))
        if not req.con.execute("SELECT 1 FROM task_photos WHERE task_id = ? AND photo_id = ?", (t["id"], req.match["pid"])).fetchone():
            raise ApiError(404, "not_found", "Fotoğraf bu işe ait değil.")
        n = req.con.execute("SELECT COUNT(*) FROM annotations WHERE photo_id = ?", (req.match["pid"],)).fetchone()[0] + 1
        req.con.execute("INSERT INTO annotations(id, photo_id, x, y, text, by_id, created_at) VALUES (?,?,?,?,?,?,?)",
                        (db.new_id(), req.match["pid"], round(x, 2), round(y, 2), text, req.user["id"], db.now()))
        req.con.execute("INSERT INTO comments(id, task_id, by_id, text, created_at) VALUES (?,?,?,?,?)",
                        (db.new_id(), t["id"], req.user["id"], f"İşaret {n}: {text}", db.now()))
        log(req.con, t["id"], req.user["id"], f"Fotoğrafa {n}. işareti koydu")
        touch(req.con, t["id"])
    req.publish({"type": "task", "id": t["id"]})
    return {"ok": True}


@route("DELETE", r"/api/annotations/(?P<aid>\w+)")
def delete_annotation(req):
    with db.tx(req.con):
        a = req.con.execute("SELECT * FROM annotations WHERE id = ?", (req.match["aid"],)).fetchone()
        if not a:
            raise ApiError(404, "not_found", "İşaret bulunamadı.")
        if req.user["role"] != "manager" and a["by_id"] != req.user["id"]:
            raise ApiError(403, "forbidden", "Yalnızca kendi işaretini silebilirsin.")
        req.con.execute("DELETE FROM annotations WHERE id = ?", (a["id"],))
    req.publish({"type": "photo", "id": a["photo_id"]})
    return {"ok": True}


# ---------- yorum, kontrol listesi, imza ----------

@route("POST", r"/api/tasks/(?P<tid>\w+)/comments")
def add_comment(req):
    text = text_field(req.json(), "text", max_len=2000)
    with db.tx(req.con):
        t = get_task(req, req.match["tid"])
        req.con.execute("INSERT INTO comments(id, task_id, by_id, text, created_at) VALUES (?,?,?,?,?)",
                        (db.new_id(), t["id"], req.user["id"], text, db.now()))
        touch(req.con, t["id"])
    req.publish({"type": "task", "id": t["id"]})
    return {"ok": True}


@route("POST", r"/api/tasks/(?P<tid>\w+)/checklist")
def add_check(req):
    body = req.json()
    text = text_field(body, "text", max_len=200)
    with db.tx(req.con):
        t = get_task(req, req.match["tid"], for_write=True)
        sort = req.con.execute("SELECT COALESCE(MAX(sort), 0) + 1 FROM checklist WHERE task_id = ?", (t["id"],)).fetchone()[0]
        req.con.execute("INSERT INTO checklist(id, task_id, text, require_proof, sort) VALUES (?,?,?,?,?)",
                        (db.new_id(), t["id"], text, 1 if body.get("require_proof") else 0, sort))
        log(req.con, t["id"], req.user["id"], f"Kontrol maddesi ekledi: {text}")
        touch(req.con, t["id"])
    req.publish({"type": "task", "id": t["id"]})
    return {"ok": True}


@route("PATCH", r"/api/checklist/(?P<cid>\w+)")
def update_check(req):
    body = req.json()
    with db.tx(req.con):
        c = req.con.execute("SELECT * FROM checklist WHERE id = ?", (req.match["cid"],)).fetchone()
        if not c:
            raise ApiError(404, "not_found", "Madde bulunamadı.")
        t = get_task(req, c["task_id"], for_write=True)
        proof = c["proof_photo_id"]
        if "proof_photo_id" in body:
            proof = body["proof_photo_id"] or None
            if proof and not req.con.execute("SELECT 1 FROM task_photos WHERE task_id = ? AND photo_id = ?", (t["id"], proof)).fetchone():
                raise ApiError(400, "bad_photo", "Kanıt fotoğrafı bu işe ait olmalı.")
        done = bool(body.get("done", c["done"]))
        if done and c["require_proof"] and not proof:
            raise ApiError(400, "proof_required", f"“{c['text']}” maddesi için kanıt fotoğrafı zorunlu. Önce fotoğraf bağla.")
        req.con.execute("UPDATE checklist SET done = ?, proof_photo_id = ? WHERE id = ?", (1 if done else 0, proof, c["id"]))
        if "proof_photo_id" in body and proof:
            log(req.con, t["id"], req.user["id"], f"“{c['text']}” maddesine kanıt fotoğrafı bağladı")
        if done != bool(c["done"]):
            log(req.con, t["id"], req.user["id"], f"“{c['text']}” {'tamamlandı' if done else 'geri alındı'}")
        automation = {"moved": False, "message": None}
        if req.con.execute("SELECT 1 FROM task_photos WHERE task_id = ? AND type = 'after' LIMIT 1", (t["id"],)).fetchone():
            automation = run_automation(req.con, t["id"])  # son eksik kanıt tamamlandıysa işi onaya taşı
            if not automation["moved"]:
                automation["message"] = None
        touch(req.con, t["id"])
    req.publish({"type": "task", "id": t["id"]})
    return {"ok": True, "automation": automation}


@route("DELETE", r"/api/checklist/(?P<cid>\w+)")
def delete_check(req):
    with db.tx(req.con):
        c = req.con.execute("SELECT * FROM checklist WHERE id = ?", (req.match["cid"],)).fetchone()
        if not c:
            raise ApiError(404, "not_found", "Madde bulunamadı.")
        t = get_task(req, c["task_id"], for_write=True)
        req.con.execute("DELETE FROM checklist WHERE id = ?", (c["id"],))
        log(req.con, t["id"], req.user["id"], f"Kontrol maddesini sildi: {c['text']}")
        touch(req.con, t["id"])
    req.publish({"type": "task", "id": t["id"]})
    return {"ok": True}


@route("POST", r"/api/tasks/(?P<tid>\w+)/signature")
def save_signature(req):
    signer = (req.query.get("signer") or "").strip()[:80]
    if not signer:
        raise ApiError(400, "missing_field", "İmzalayan kişinin adı gerekli.")
    data = req.body(limit=2 * 1024 * 1024)
    if images.sniff(data) != "png":
        raise ApiError(415, "unsupported_type", "İmza PNG olmalı.")
    with db.tx(req.con):
        t = get_task(req, req.match["tid"], for_write=True)
        sig_dir = os.path.join(req.cfg.data_dir, "signatures")
        os.makedirs(sig_dir, exist_ok=True)
        name = f"{t['id']}.png"
        with open(os.path.join(sig_dir, name), "wb") as f:
            f.write(data)
        req.con.execute("INSERT INTO signatures(task_id, path, signer, created_at) VALUES (?,?,?,?) "
                        "ON CONFLICT(task_id) DO UPDATE SET path = excluded.path, signer = excluded.signer, created_at = excluded.created_at",
                        (t["id"], name, signer, db.now()))
        log(req.con, t["id"], req.user["id"], f"Müşteri imzası alındı: {signer}")
        touch(req.con, t["id"])
    req.publish({"type": "task", "id": t["id"]})
    return {"ok": True}


@route("GET", r"/files/signature/(?P<tid>\w+)")
def signature_file(req):
    get_task(req, req.match["tid"])
    row = req.con.execute("SELECT path FROM signatures WHERE task_id = ?", (req.match["tid"],)).fetchone()
    if not row:
        raise ApiError(404, "not_found", "İmza yok.")
    return req.file(os.path.join(req.cfg.data_dir, "signatures", row["path"]), "image/png")


# ---------- yedek ----------

@route("GET", "/api/backup")
def backup(req):
    need_manager(req)
    tmp = tempfile.mkdtemp(prefix="fototakip-backup-")
    try:
        snap = os.path.join(tmp, "fototakip.db")
        dst = sqlite3.connect(snap)
        with db.WRITE_LOCK:
            req.con.backup(dst)
        dst.close()
        stamp = datetime.now().strftime("%Y%m%d-%H%M")
        zpath = os.path.join(tmp, f"fototakip-yedek-{stamp}.zip")
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_STORED) as z:
            z.write(snap, "fototakip.db")
            for sub in ("photos", "signatures"):
                base = os.path.join(req.cfg.data_dir, sub)
                if os.path.isdir(base):
                    for name in os.listdir(base):
                        z.write(os.path.join(base, name), f"{sub}/{name}")
        return req.file(zpath, "application/zip", download=os.path.basename(zpath), cleanup=tmp)
    except Exception:
        shutil.rmtree(tmp, ignore_errors=True)
        raise


# ---------- AI fotoğraf incelemesi ----------

@route("POST", r"/api/photos/(?P<pid>\w+)/ai-review")
def ai_review_photo(req):
    """Fotoğraf için AI gözlemi. Karar vermez; yalnızca insan incelemesine not üretir."""
    body = req.json()
    con, pid = req.con, req.match["pid"]
    if db.setting(con, "ai_enabled", "0") != "1":
        raise ApiError(409, "ai_disabled", "AI inceleme kapalı. Yönetici Profil › Entegrasyonlar'dan açabilir.")
    t = get_task(req, body.get("task_id", ""))
    if not con.execute("SELECT 1 FROM task_photos WHERE task_id = ? AND photo_id = ?", (t["id"], pid)).fetchone():
        raise ApiError(404, "not_found", "Fotoğraf bu işe ait değil.")
    cached = con.execute("SELECT * FROM ai_reviews WHERE photo_id = ?", (pid,)).fetchone()
    if cached and not (body.get("force") and req.user["role"] == "manager"):
        return {**json.loads(cached["result"]), "by": cached["by_id"], "at": cached["created_at"], "cached": True}
    ph = con.execute("SELECT * FROM photos WHERE id = ?", (pid,)).fetchone()
    p = con.execute("SELECT name FROM projects WHERE id = ?", (t["project_id"],)).fetchone()
    ptype = con.execute("SELECT type FROM task_photos WHERE task_id = ? AND photo_id = ?", (t["id"], pid)).fetchone()["type"]
    context = f"İş: {t['title']}. Müşteri/saha: {p['name'] if p else ''}. Fotoğraf türü: {TYPES[ptype]}."
    try:
        result = ai_review.review_photo(os.path.join(req.cfg.data_dir, "photos", ph["path"]), ph["mime"], context,
                                        api_key=secrets.get(req.cfg.data_dir, "openai_api_key"),
                                        model=db.setting(con, "ai_model", ai_review.DEFAULT_MODEL))
    except ai_review.ReviewError as e:
        raise ApiError(502 if "servis" in str(e) or "limit" in str(e) else 400, "ai_error", str(e))
    at = db.now()
    with db.tx(con):
        con.execute("INSERT OR REPLACE INTO ai_reviews(photo_id, model, result, by_id, created_at) VALUES (?,?,?,?,?)",
                    (pid, result["model"], json.dumps(result, ensure_ascii=False), req.user["id"], at))
        crit = sum(1 for o in result["observations"] if o["level"] == "critical")
        log(con, t["id"], req.user["id"], f"AI gözlemi alındı ({TYPES[ptype]} fotoğrafı{f', {crit} kritik not' if crit else ''})")
        touch(con, t["id"])
    req.publish({"type": "task", "id": t["id"]})
    return {**result, "by": req.user["id"], "at": at, "cached": False}


# ---------- entegrasyonlar: AI, tünel, DNS ----------

DEMO_PASSWORD = "demo1234"


def demo_password_users(con) -> list[str]:
    return [r["username"] for r in con.execute("SELECT username, pw_hash FROM users")
            if auth.verify_password(DEMO_PASSWORD, r["pw_hash"])]


def integrations_state(req) -> dict:
    con, d = req.con, req.cfg.data_dir
    key, token = secrets.get(d, "openai_api_key"), secrets.get(d, "tunnel_token")
    return {
        "ai": {"enabled": db.setting(con, "ai_enabled", "0") == "1", "model": db.setting(con, "ai_model", ai_review.DEFAULT_MODEL),
               "key_set": bool(key), "key_hint": secrets.hint(key)},
        "tunnel": {"mode": db.setting(con, "tunnel_mode", "off"), "hostname": db.setting(con, "tunnel_hostname", ""),
                   "autostart": db.setting(con, "tunnel_autostart", "0") == "1", "token_set": bool(token),
                   "token_hint": secrets.hint(token), **{f"run_{k}": v for k, v in req.tunnel.snapshot().items()}},
        "dns": tunnel.read_dns(),
        "demo_password_users": demo_password_users(con),
        "local_port": req.cfg.port,
    }


@route("GET", "/api/admin/integrations")
def get_integrations(req):
    need_manager(req)
    return integrations_state(req)


@route("PATCH", "/api/admin/integrations")
def update_integrations(req):
    need_manager(req)
    body, con, d = req.json(), req.con, req.cfg.data_dir
    ai = body.get("ai") or {}
    tn = body.get("tunnel") or {}
    if "openai_key" in ai:
        k = (ai["openai_key"] or "").strip()
        if k and not re.fullmatch(r"sk-[A-Za-z0-9_\-]{20,}", k):
            raise ApiError(400, "bad_key", "Bu bir OpenAI API anahtarına benzemiyor (sk- ile başlamalı).")
        secrets.put(d, "openai_api_key", k or None)
    if "tunnel_token" in tn:
        tok = (tn["tunnel_token"] or "").strip()
        if tok and not re.fullmatch(r"[A-Za-z0-9_\-=.]{40,}", tok):
            raise ApiError(400, "bad_token", "Cloudflare tünel token'ı geçersiz görünüyor. Zero Trust panelindeki 'cloudflared tunnel run --token' satırının sonundaki uzun değeri yapıştır.")
        secrets.put(d, "tunnel_token", tok or None)
    with db.tx(con):
        if "enabled" in ai:
            db.set_setting(con, "ai_enabled", "1" if ai["enabled"] else "0")
        if "model" in ai:
            m = (ai["model"] or "").strip()
            if not re.fullmatch(r"[A-Za-z0-9._:\-]{2,64}", m):
                raise ApiError(400, "bad_model", "Model adı geçersiz.")
            db.set_setting(con, "ai_model", m)
        if "mode" in tn:
            if tn["mode"] not in ("off", "quick", "named"):
                raise ApiError(400, "bad_mode", "Tünel türü off, quick veya named olmalı.")
            db.set_setting(con, "tunnel_mode", tn["mode"])
        if "hostname" in tn:
            h = (tn["hostname"] or "").strip().lower().removeprefix("https://").removeprefix("http://").strip("/")
            if h and not re.fullmatch(r"[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+", h):
                raise ApiError(400, "bad_hostname", "Alan adı geçersiz (ör. is.alanadin.com).")
            db.set_setting(con, "tunnel_hostname", h)
        if "autostart" in tn:
            db.set_setting(con, "tunnel_autostart", "1" if tn["autostart"] else "0")
    if body.get("dns"):
        try:
            tunnel.write_dns(body["dns"])
        except ValueError as e:
            raise ApiError(400, "dns", str(e))
        except OSError as e:
            raise ApiError(500, "dns_write", f"DNS dosyası yazılamadı: {e.strerror}")
    req.publish({"type": "settings"})
    return integrations_state(req)


def start_tunnel(con, cfg, tun) -> dict:
    mode = db.setting(con, "tunnel_mode", "off")
    if mode == "off":
        raise ApiError(400, "tunnel_off", "Önce tünel türünü seç.")
    users = demo_password_users(con)
    if users:
        raise ApiError(409, "demo_passwords", "Örnek hesapların parolası hâlâ demo1234: " + ", ".join(users)
                       + ". İnternete açmadan önce bu hesapların parolasını değiştir ya da hesapları kullanma.")
    return tun.start(mode, secrets.get(cfg.data_dir, "tunnel_token"), db.setting(con, "tunnel_hostname", ""))


@route("POST", "/api/admin/tunnel/start")
def tunnel_start(req):
    need_manager(req)
    start_tunnel(req.con, req.cfg, req.tunnel)
    return integrations_state(req)


@route("POST", "/api/admin/tunnel/stop")
def tunnel_stop(req):
    need_manager(req)
    req.tunnel.stop()
    return integrations_state(req)


@route("POST", r"/api/admin/users/(?P<uid>\w+)/password")
def reset_user_password(req):
    """Yönetici başka bir kişinin parolasını sıfırlar (örnek hesapları kapatmak için)."""
    need_manager(req)
    new = req.json().get("password") or ""
    if len(new) < 8:
        raise ApiError(400, "weak_password", "Yeni parola en az 8 karakter olmalı.")
    with db.tx(req.con):
        cur = req.con.execute("UPDATE users SET pw_hash = ? WHERE id = ?", (auth.hash_password(new), req.match["uid"]))
        if not cur.rowcount:
            raise ApiError(404, "not_found", "Kişi bulunamadı.")
        # o kişinin diğer oturumları kapanır; kendi parolasını değiştiren yönetici açık kalır
        req.con.execute("DELETE FROM sessions WHERE user_id = ? AND token != ?", (req.match["uid"], req.token or ""))
    return {"ok": True}
