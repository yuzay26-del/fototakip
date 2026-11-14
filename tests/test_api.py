"""API uçtan uca testleri. Gerçek sunucuyu geçici klasörde başlatır; yalnızca standart kütüphane."""

import base64
import io
import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fototakip import db, images  # noqa: E402
import ornek_veri as seed  # noqa: E402
from fototakip.server import Config, make_server  # noqa: E402

# 64x48 JPEG: EXIF yönü 6, çekim zamanı 2026-10-30 09:14:59, GPS 40.9862 K / 29.0270 D
JPEG_GPS = base64.b64decode(
    "/9j/4AAQSkZJRgABAQAAAQABAAD/4QDmRXhpZgAATU0AKgAAAAgABAESAAMAAAABAAYAAAEyAAIAAAAUAAAAPodpAAQAAAAB"
    "AAAAUoglAAQAAAABAAAAeAAAAAAyMDI2OjEwOjMwIDA5OjE1OjAwAAABkAMAAgAAABQAAABkAAAAADIwMjY6MTA6MzAgMDk6"
    "MTQ6NTkAAAQAAQACAAAAAk4AAAAAAgAFAAAAAwAAAK4AAwACAAAAAkUAAAAABAAFAAAAAwAAAMYAAAAAAAAAKAAAAAEAAAA7"
    "AAAAAQAAAQIAAAAZAAAAHQAAAAEAAAABAAAAAQAAALoAAAAF/9sAQwAKBwcIBwYKCAgICwoKCw4YEA4NDQ4dFRYRGCMfJSQi"
    "HyIhJis3LyYpNCkhIjBBMTQ5Oz4+PiUuRElDPEg3PT47/9sAQwEKCwsODQ4cEBAcOygiKDs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7"
    "Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7/8AAEQgAMABAAwEiAAIRAQMRAf/EAB8AAAEFAQEBAQEBAAAAAAAAAAAB"
    "AgMEBQYHCAkKC//EALUQAAIBAwMCBAMFBQQEAAABfQECAwAEEQUSITFBBhNRYQcicRQygZGhCCNCscEVUtHwJDNicoIJChYX"
    "GBkaJSYnKCkqNDU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6g4SFhoeIiYqSk5SVlpeYmZqio6Slpqeo"
    "qaqys7S1tre4ubrCw8TFxsfIycrS09TV1tfY2drh4uPk5ebn6Onq8fLz9PX29/j5+v/EAB8BAAMBAQEBAQEBAQEAAAAAAAAB"
    "AgMEBQYHCAkKC//EALURAAIBAgQEAwQHBQQEAAECdwABAgMRBAUhMQYSQVEHYXETIjKBCBRCkaGxwQkjM1LwFWJy0QoWJDTh"
    "JfEXGBkaJicoKSo1Njc4OTpDREVGR0hJSlNUVVZXWFlaY2RlZmdoaWpzdHV2d3h5eoKDhIWGh4iJipKTlJWWl5iZmqKjpKWm"
    "p6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uLj5OXm5+jp6vLz9PX29/j5+v/aAAwDAQACEQMRAD8AmooorqOUKKKK"
    "ACiiigAooooAKKi+yW3/AD7xf98Cj7Jbf8+8X/fAqby7GtqXd/d/wSWiovslt/z7xf8AfAo+yW3/AD7xf98Ci8uwWpd393/B"
    "JaKi+yW3/PvF/wB8Cj7Jbf8APvF/3wKLy7Bal3f3f8EloqL7Jbf8+8X/AHwKPslt/wA+8X/fAovLsFqXd/d/wSWiiiqMgooo"
    "oAKKKKACiiigD//Z"
)
JPEG_A = base64.b64decode(
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAoHBwgHBgoICAgLCgoLDhgQDg0NDh0VFhEYIx8lJCIfIiEmKzcvJik0KSEiMEEx"
    "NDk7Pj4+JS5ESUM8SDc9Pjv/2wBDAQoLCw4NDhwQEBw7KCIoOzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7"
    "Ozs7Ozs7Ozs7Ozs7Ozv/wAARCAAeACgDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAA"
    "AgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6"
    "Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXG"
    "x8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREA"
    "AgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5"
    "OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPE"
    "xcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwCnRRRXKfIBRRRQAUUUUAFFFFABRRRQAUUU"
    "UAf/2Q=="
)
JPEG_B = base64.b64decode(
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAoHBwgHBgoICAgLCgoLDhgQDg0NDh0VFhEYIx8lJCIfIiEmKzcvJik0KSEiMEEx"
    "NDk7Pj4+JS5ESUM8SDc9Pjv/2wBDAQoLCw4NDhwQEBw7KCIoOzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7"
    "Ozs7Ozs7Ozs7Ozs7Ozv/wAARCAAeACgDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAA"
    "AgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6"
    "Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXG"
    "x8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREA"
    "AgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5"
    "OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPE"
    "xcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDMooor50+gCiiigAooooAKKKKACiiigAoo"
    "ooA//9k="
)
PNG_1PX = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==")
HEIC = b"\x00\x00\x00\x18ftypheic\x00\x00\x00\x00mif1heic" + b"\x00" * 64


class Client:
    def __init__(self, base):
        self.base, self.token = base, None

    def call(self, method, path, body=None, raw=None, ctype=None):
        headers = {}
        data = None
        if raw is not None:
            data, headers["Content-Type"] = raw, ctype or "image/jpeg"
        elif body is not None:
            data, headers["Content-Type"] = json.dumps(body).encode(), "application/json"
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        req = urllib.request.Request(self.base + path, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                payload = r.read()
                ct = r.headers.get("Content-Type", "")
                return r.status, (json.loads(payload) if ct.startswith("application/json") else payload)
        except urllib.error.HTTPError as e:
            payload = e.read()
            try:
                return e.code, json.loads(payload)
            except ValueError:
                return e.code, payload

    def login(self, username, password=seed.DEMO_PASSWORD):
        status, body = self.call("POST", "/api/login", {"username": username, "password": password})
        assert status == 200, body
        self.token = body["token"]
        return self

    def boot(self):
        return self.call("GET", "/api/bootstrap")[1]


class ApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cfg = Config(host="127.0.0.1", port=0, data_dir=cls.tmp.name, quiet=True, geocoder="off")
        cls.server = make_server(cfg)
        seed.seed_demo(cfg.db_path, cfg.data_dir)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.tmp.cleanup()

    def c(self, user=None):
        cl = Client(self.base)
        return cl.login(user) if user else cl

    def task_by_no(self, boot, no):
        return next(t for t in boot["tasks"] if t["no_label"] == f"İE-{no:04d}")

    def project(self, boot, short):
        return next(p for p in boot["projects"] if p["short"] == short)

    # ---- temel ----
    def test_health_and_static(self):
        cl = self.c()
        status, body = cl.call("GET", "/api/health")
        self.assertEqual(status, 200)
        self.assertFalse(body["needs_setup"])
        status, html = cl.call("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b"FotoTakip", html)
        self.assertEqual(cl.call("GET", "/kanban")[0], 200)  # tek sayfa uygulama yönlendirmesi
        self.assertEqual(cl.call("GET", "/yok.js")[0], 404)
        self.assertEqual(cl.call("GET", "/../fototakip/db.py")[0], 404)

    def test_auth_required_and_bad_login(self):
        cl = self.c()
        status, body = cl.call("GET", "/api/bootstrap")
        self.assertEqual(status, 401)
        self.assertEqual(body["error"]["code"], "unauthorized")
        status, body = cl.call("POST", "/api/login", {"username": "yonetici", "password": "yanlis"})
        self.assertEqual(status, 401)

    def test_field_sees_only_own_tasks(self):
        mert = self.c("saha1").boot()
        elif_ = self.c("saha2").boot()
        mgr = self.c("yonetici").boot()
        mert_ids = {t["id"] for t in mert["tasks"]}
        for t in mgr["tasks"]:  # havuzdaki (atanmamış) işler de görünmez
            self.assertEqual(t["id"] in mert_ids, t["assignee_id"] == mert["me"]["id"], t["no_label"])
        self.assertNotIn(self.task_by_no(mgr, 142)["id"], mert_ids)
        self.assertIn(self.task_by_no(mgr, 142)["id"], {t["id"] for t in elif_["tasks"]})

    # ---- fotoğraf ----
    def test_photo_upload_creates_task_with_exif(self):
        cl = self.c("saha1")
        p = self.project(cl.boot(), "Maltepe")
        status, r = cl.call("POST", f"/api/photos?type=issue&new_task=1&project_id={p['id']}", raw=JPEG_GPS)
        self.assertEqual(status, 200, r)
        self.assertFalse(r["duplicate"])
        b = cl.boot()
        t = next(t for t in b["tasks"] if t["id"] == r["task_id"])
        self.assertTrue(t["untitled"])
        self.assertEqual(t["assignee_id"], b["me"]["id"])
        ph = b["photos"][r["photo_id"]]
        self.assertEqual(ph["gps_source"], "exif")
        self.assertAlmostEqual(ph["lat"], 40.9862, places=3)
        self.assertTrue(ph["taken_at"].startswith("2026-10-30T09:14"))
        status, data = cl.call("GET", f"/files/{r['photo_id']}")
        self.assertEqual(status, 200)
        if images.HAVE_PIL:
            self.assertNotIn(b"Exif", data[:200], "Kaydedilen dosyada EXIF/GPS kalmamalı")
            self.assertEqual(ph["width"], 48)  # yön düzeltildi: 64x48 -> 48x64
        # aynı fotoğraf aynı işe tekrar: kopya
        status, r2 = cl.call("POST", f"/api/photos?type=issue&task_id={r['task_id']}", raw=JPEG_GPS)
        self.assertTrue(r2["duplicate"])
        self.assertEqual(len(next(t for t in cl.boot()["tasks"] if t["id"] == r["task_id"])["photos"]), 1)

    def test_photo_rejects_bad_types(self):
        cl = self.c("yonetici")
        t = self.task_by_no(cl.boot(), 143)
        status, body = cl.call("POST", f"/api/photos?type=issue&task_id={t['id']}", raw=HEIC)
        self.assertEqual(status, 415)
        self.assertEqual(body["error"]["code"], "heic_unsupported")
        status, body = cl.call("POST", f"/api/photos?type=issue&task_id={t['id']}", raw=b"<svg onload=alert(1)>")
        self.assertEqual(status, 415)
        status, body = cl.call("POST", f"/api/photos?type=kotu&task_id={t['id']}", raw=JPEG_A)
        self.assertEqual(status, 400)

    def test_field_cannot_see_others_photo(self):
        mgr = self.c("yonetici").boot()
        t = self.task_by_no(mgr, 142)  # saha2'nin işi
        pid = t["photos"][0]["pid"]
        self.assertEqual(self.c("saha1").call("GET", f"/files/{pid}")[0], 404)
        self.assertEqual(self.c("saha2").call("GET", f"/files/{pid}")[0], 200)

    # ---- otomasyon ve onay ----
    def test_automation_requires_before_photo(self):
        cl = self.c("yonetici")
        p = self.project(cl.boot(), "Kadıköy")
        status, r = cl.call("POST", f"/api/photos?type=after&new_task=1&project_id={p['id']}&title=Sadece%20sonra", raw=JPEG_A)
        self.assertEqual(status, 200)
        self.assertFalse(r["automation"]["moved"])
        self.assertIn("Önce fotoğrafı", r["automation"]["message"])
        self.assertEqual(next(t for t in cl.boot()["tasks"] if t["id"] == r["task_id"])["status"], "open")

    def test_automation_and_proof_and_review(self):
        mgr = self.c("yonetici")
        mert = self.c("saha1")
        t = self.task_by_no(mert.boot(), 141)  # önce fotoğrafı var, 1 zorunlu madde kanıtsız
        status, r = mert.call("POST", f"/api/photos?type=after&task_id={t['id']}", raw=JPEG_B)
        self.assertFalse(r["automation"]["moved"])
        self.assertIn("zorunlu", r["automation"]["message"])
        t = self.task_by_no(mert.boot(), 141)
        req = next(c for c in t["checklist"] if c["require_proof"])
        status, body = mert.call("PATCH", f"/api/checklist/{req['id']}", {"done": True})
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "proof_required")
        status, body = mert.call("PATCH", f"/api/checklist/{req['id']}", {"done": True, "proof_photo_id": r["photo_id"]})
        self.assertEqual(status, 200)
        self.assertTrue(body["automation"]["moved"], "Son zorunlu kanıt gelince iş onaya taşınmalı")
        self.assertEqual(self.task_by_no(mert.boot(), 141)["status"], "review")
        # saha rolü tamamlayamaz
        t = self.task_by_no(mert.boot(), 141)
        status, body = mert.call("PATCH", f"/api/tasks/{t['id']}", {"status": "done", "version": t["version"]})
        self.assertEqual(status, 403)
        status, _ = mert.call("PATCH", f"/api/tasks/{t['id']}", {"status": "review", "version": t["version"]})
        self.assertEqual(status, 200)
        # gerekçesiz geri gönderme reddedilir
        status, body = mgr.call("POST", f"/api/tasks/{t['id']}/review", {"decision": "reject"})
        self.assertEqual(status, 400)
        status, _ = mgr.call("POST", f"/api/tasks/{t['id']}/review", {"decision": "reject", "reason": "Tavan hâlâ nemli"})
        self.assertEqual(status, 200)
        t = self.task_by_no(mert.boot(), 141)
        self.assertEqual(t["status"], "progress")
        self.assertEqual(t["rejected_reason"], "Tavan hâlâ nemli")
        mert.call("PATCH", f"/api/tasks/{t['id']}", {"status": "review"})
        status, _ = mgr.call("POST", f"/api/tasks/{t['id']}/review", {"decision": "approve"})
        self.assertEqual(status, 200)
        t = self.task_by_no(mgr.boot(), 141)
        self.assertEqual(t["status"], "done")
        self.assertIsNone(t["rejected_reason"])

    def test_version_conflict(self):
        cl = self.c("yonetici")
        t = self.task_by_no(cl.boot(), 146)
        status, _ = cl.call("PATCH", f"/api/tasks/{t['id']}", {"title": "Oluk temizliği ve kontrol", "version": t["version"]})
        self.assertEqual(status, 200)
        status, body = cl.call("PATCH", f"/api/tasks/{t['id']}", {"status": "review", "version": t["version"]})
        self.assertEqual(status, 409)
        self.assertEqual(body["error"]["code"], "conflict")

    def test_pool_hidden_from_field(self):
        mgr = self.c("yonetici")
        p = self.project(mgr.boot(), "Ataşehir")
        _, r = mgr.call("POST", "/api/tasks", {"project_id": p["id"], "title": "Havuz testi"})
        elif_ = self.c("saha2")
        self.assertNotIn(r["id"], {t["id"] for t in elif_.boot()["tasks"]})
        self.assertEqual(elif_.call("PATCH", f"/api/tasks/{r['id']}", {"title": "x"})[0], 404)
        self.assertEqual(elif_.call("POST", f"/api/tasks/{r['id']}/claim")[0], 404)
        saha2 = next(u["id"] for u in mgr.boot()["users"] if u["username"] == "saha2")
        self.assertEqual(mgr.call("PATCH", f"/api/tasks/{r['id']}", {"assignee_id": saha2})[0], 200)
        self.assertIn(r["id"], {t["id"] for t in elif_.boot()["tasks"]})

    # ---- diğerleri ----
    def test_annotation_comment_search_signature(self):
        cl = self.c("yonetici")
        t = self.task_by_no(cl.boot(), 143)
        pid = t["photos"][0]["pid"]
        status, _ = cl.call("POST", f"/api/photos/{pid}/annotations", {"task_id": t["id"], "x": 12.5, "y": 80, "text": "Topraklama hattı eksik"})
        self.assertEqual(status, 200)
        self.assertEqual(cl.call("POST", f"/api/photos/{pid}/annotations", {"task_id": t["id"], "x": 120, "y": 5, "text": "x"})[0], 400)
        status, r = cl.call("GET", "/api/search?q=" + urllib.parse.quote("topraklama"))
        self.assertEqual(r["ids"], [t["id"]])
        status, _ = cl.call("POST", f"/api/tasks/{t['id']}/signature?signer=" + urllib.parse.quote("Test İmzacı"), raw=PNG_1PX, ctype="image/png")
        self.assertEqual(status, 200)
        t = self.task_by_no(cl.boot(), 143)
        self.assertEqual(t["signature"]["signer"], "Test İmzacı")
        self.assertEqual(cl.call("GET", f"/files/signature/{t['id']}")[0], 200)

    def test_users_projects_settings_backup(self):
        mgr = self.c("yonetici")
        self.assertEqual(self.c("saha1").call("POST", "/api/users", {"username": "x", "name": "X", "password": "123456"})[0], 403)
        status, _ = mgr.call("POST", "/api/users", {"username": "ali.usta", "name": "Ali Usta", "password": "gizli123", "role": "field"})
        self.assertEqual(status, 200)
        self.assertEqual(mgr.call("POST", "/api/users", {"username": "ali.usta", "name": "Ali", "password": "gizli123"})[0], 409)
        ali = Client(self.base).login("ali.usta", "gizli123")
        self.assertEqual(ali.boot()["me"]["role"], "field")
        status, _ = mgr.call("POST", "/api/projects", {"name": "Üsküdar · Okul", "lat": "41.02", "lng": "29.01"})
        self.assertEqual(status, 200)
        self.assertEqual(mgr.call("POST", "/api/projects", {"name": "Hatalı", "lat": "200"})[0], 400)
        mgr.call("PATCH", "/api/settings", {"auto_rule": False})
        self.assertFalse(mgr.boot()["settings"]["auto_rule"])
        mgr.call("PATCH", "/api/settings", {"auto_rule": True})
        status, data = mgr.call("GET", "/api/backup")
        self.assertEqual(status, 200)
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            names = z.namelist()
        self.assertIn("fototakip.db", names)
        self.assertTrue(any(n.startswith("photos/") for n in names))

    def test_password_change(self):
        mgr = self.c("yonetici")
        mgr.call("POST", "/api/users", {"username": "deneme", "name": "Deneme Kişi", "password": "eskiparola"})
        u = Client(self.base).login("deneme", "eskiparola")
        self.assertEqual(u.call("PATCH", "/api/me/password", {"old": "yanlis", "new": "yeniparola"})[0], 400)
        self.assertEqual(u.call("PATCH", "/api/me/password", {"old": "eskiparola", "new": "yeniparola"})[0], 200)
        Client(self.base).login("deneme", "yeniparola")

    def test_too_large_upload(self):
        cl = self.c("yonetici")
        t = self.task_by_no(cl.boot(), 145)
        big = b"\xff\xd8\xff" + b"0" * (16 * 1024 * 1024)
        status, body = cl.call("POST", f"/api/photos?type=issue&task_id={t['id']}", raw=big)
        self.assertEqual(status, 413)


    # ---- 0.5.1: silme, yedek, sağlamlık ----
    def _photos_on_disk(self, pid):
        return [n for n in os.listdir(os.path.join(self.tmp.name, "photos")) if n.startswith(pid)]

    def test_deleted_task_removes_photo_and_signature_files(self):
        mgr = self.c("yonetici")
        p = self.project(mgr.boot(), "Kadıköy")
        status, r = mgr.call("POST", f"/api/photos?type=before&new_task=1&project_id={p['id']}&title=Silinecek", raw=JPEG_A + b"sil-1")
        self.assertEqual(status, 200)
        tid, pid = r["task_id"], r["photo_id"]
        self.assertEqual(mgr.call("POST", f"/api/tasks/{tid}/signature?signer=Deneme", raw=PNG_1PX, ctype="image/png")[0], 200)
        sig = os.path.join(self.tmp.name, "signatures", f"{tid}.png")
        self.assertTrue(self._photos_on_disk(pid))
        self.assertTrue(os.path.isfile(sig))
        self.assertEqual(mgr.call("DELETE", f"/api/tasks/{tid}")[0], 200)
        self.assertEqual(mgr.call("GET", f"/files/{pid}")[0], 404)
        self.assertEqual(self._photos_on_disk(pid), [], "Silinen işin fotoğraf dosyaları diskte kalmamalı")
        self.assertFalse(os.path.isfile(sig), "Silinen işin imza dosyası diskte kalmamalı")

    def test_shared_photo_survives_until_last_link_removed(self):
        mgr = self.c("yonetici")
        p = self.project(mgr.boot(), "Kadıköy")
        img = JPEG_A + b"ortak-1"
        _, a = mgr.call("POST", f"/api/photos?type=issue&new_task=1&project_id={p['id']}&title=Ortak%20A", raw=img)
        _, b = mgr.call("POST", f"/api/photos?type=issue&new_task=1&project_id={p['id']}&title=Ortak%20B", raw=img)
        pid = a["photo_id"]
        self.assertEqual(b["photo_id"], pid)
        self.assertTrue(b["already_stored"])
        self.assertEqual(mgr.call("DELETE", f"/api/tasks/{a['task_id']}/photos/{pid}")[0], 200)
        self.assertEqual(mgr.call("GET", f"/files/{pid}")[0], 200, "Başka işe bağlı fotoğraf silinmemeli")
        self.assertTrue(self._photos_on_disk(pid))
        self.assertEqual(mgr.call("DELETE", f"/api/tasks/{b['task_id']}/photos/{pid}")[0], 200)
        self.assertEqual(mgr.call("GET", f"/files/{pid}")[0], 404)
        self.assertEqual(self._photos_on_disk(pid), [])
        # aynı fotoğraf sonradan yeniden yüklenebilir
        status, c = mgr.call("POST", f"/api/photos?type=issue&task_id={b['task_id']}", raw=img)
        self.assertEqual(status, 200)
        self.assertFalse(c["already_stored"])

    def test_backup_has_no_sessions(self):
        import sqlite3
        mgr = self.c("yonetici")
        status, data = mgr.call("GET", "/api/backup")
        self.assertEqual(status, 200)
        with tempfile.TemporaryDirectory() as d:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                z.extract("fototakip.db", d)
            con = sqlite3.connect(os.path.join(d, "fototakip.db"))
            try:
                self.assertEqual(con.execute("SELECT COUNT(*) FROM sessions").fetchone()[0], 0, "Yedekte açık oturum olmamalı")
                self.assertGreater(con.execute("SELECT COUNT(*) FROM users").fetchone()[0], 0)
                self.assertEqual(con.execute("SELECT COUNT(*) FROM settings WHERE key LIKE 'setup_%'").fetchone()[0], 0)
            finally:
                con.close()
            with open(os.path.join(d, "fototakip.db"), "rb") as f:
                self.assertNotIn(mgr.token.encode(), f.read(), "Oturum anahtarı yedek dosyasında iz bırakmamalı")
        self.assertEqual(mgr.call("GET", "/api/bootstrap")[0], 200, "Yedek almak açık oturumu kapatmamalı")

    def test_malformed_input_is_rejected_not_crashed(self):
        import http.client
        cl = Client(self.base)
        self.assertEqual(cl.call("POST", "/api/login", {"username": "yonetici", "password": 12345678})[0], 401)
        self.assertEqual(cl.call("POST", "/api/login", {"username": "yonetici", "password": ["x"]})[0], 401)
        mgr = self.c("yonetici")
        self.assertEqual(mgr.call("POST", "/api/projects", {"name": "Yarım konum", "lat": "41.0"})[0], 400)
        self.assertEqual(mgr.call("POST", "/api/users", {"username": "sayi.parola", "name": "Sayı", "password": 12345678})[0], 400)
        host, port = self.server.server_address[:2]
        conn = http.client.HTTPConnection(host, port, timeout=5)
        try:
            conn.putrequest("POST", "/api/login")
            conn.putheader("Content-Type", "application/json")
            conn.putheader("Content-Length", "-5")
            conn.endheaders()
            self.assertEqual(conn.getresponse().status, 400, "Eksi Content-Length bağlantıyı asmamalı")
        finally:
            conn.close()


class ExifTest(unittest.TestCase):
    def test_parse(self):
        meta = images.read_exif(JPEG_GPS)
        self.assertEqual(meta["orientation"], 6)
        self.assertEqual(meta["taken_at"], "2026-10-30T09:14:59")
        self.assertAlmostEqual(meta["lat"], 40.9862, places=4)
        self.assertAlmostEqual(meta["lng"], 29.0270, places=4)

    def test_garbage(self):
        self.assertEqual(images.read_exif(b"\xff\xd8\xff\xe1\x00\x10Exif\x00\x00MM\x00*\xff\xff\xff\xff"), {})
        self.assertEqual(images.read_exif(b"not a jpeg"), {})
        self.assertIsNone(images.sniff(b"GIF89a"))


import urllib.parse  # noqa: E402

if __name__ == "__main__":
    unittest.main()
