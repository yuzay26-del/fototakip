"""Simge paletleri ve kişisel arka plan: sahibin kuralları, kişinin seçimi, fotoğraf izolasyonu."""

import json
import os
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fototakip import api, images  # noqa: E402
from fototakip.server import Config, make_server  # noqa: E402
import ornek_veri as seed  # noqa: E402
from test_api import HEIC, JPEG_GPS, PNG_1PX, Client  # noqa: E402

PW = {"lider": seed.STRONG_PASSWORD, "yonetici2": seed.STRONG_PASSWORD}
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class ArkaPlanTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        api._FAILS.clear()
        cls.tmp = tempfile.TemporaryDirectory()
        cls.cfg = Config(host="127.0.0.1", port=0, data_dir=cls.tmp.name, quiet=True, geocoder="off")
        cls.server = make_server(cls.cfg)
        seed.seed_demo(cls.cfg.db_path, cls.cfg.data_dir)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.tmp.cleanup()

    def c(self, user):
        return Client(self.base).login(user, PW.get(user, seed.DEMO_PASSWORD))

    def rules(self, **kw):
        self.assertEqual(self.c("yonetici").call("PATCH", "/api/settings", kw)[0], 200)

    def tearDown(self):
        self.rules(bg_enabled=True, bg_choice=True, bg_upload=True)

    # ---- paletler ----
    def test_palettes_single_source(self):
        status, raw = Client(self.base).call("GET", "/palettes.json")
        self.assertEqual(status, 200)
        pals = (json.loads(raw) if isinstance(raw, bytes) else raw)["palettes"]
        icons = [i for p in pals for i in p["icons"]]
        self.assertEqual(len(icons), len(set(icons)), "bir simge yalnızca bir palette olmalı")
        self.assertEqual(tuple(icons), api.SKILL_ICONS)
        for core in ("bolt", "drop", "snow", "brush", "brick", "wifi", "wrench", "flame", "sun", "key", "cctv", "leaf"):
            self.assertIn(core, icons)  # eski yeteneklerin simgeleri geçerli kalır
        # çekirdek (null) simgeler istemcideki P sözlüğünde tanımlı olmalı
        with open(os.path.join(ROOT, "web", "app.js"), encoding="utf-8") as f:
            app = f.read()
        for p in pals:
            for name, path in p["icons"].items():
                if path is None:
                    self.assertIn(f"\n  {name}: '", app, name)
        self.assertTrue(os.path.isfile(os.path.join(ROOT, "web", "vendor", "tabler-icons-LICENSE")))

    def test_skill_accepts_palette_icon(self):
        mgr = self.c("yonetici")
        status, body = mgr.call("POST", "/api/skills", {"name": "Güneş paneli", "icon": "solar-panel", "color": "#CA8A04"})
        self.assertEqual(status, 200, body)
        self.assertEqual(mgr.call("POST", "/api/skills", {"name": "Uydurma", "icon": "yok-boyle"})[0], 400)
        mgr.call("DELETE", f"/api/skills/{body['id']}")

    # ---- kişinin seçimi ----
    def test_choose_palette_and_reset(self):
        u = self.c("saha1")
        boot = u.boot()
        self.assertIn("skills", boot["me"])
        self.assertTrue(boot["settings"]["bg_enabled"])
        self.assertEqual(boot["me"]["bg"], "")
        self.assertEqual(u.call("PATCH", "/api/me", {"bg": "pal:bahce"})[0], 200)
        self.assertEqual(u.boot()["me"]["bg"], "pal:bahce")
        for bad in ("pal:yok", "photo:abc", "http://x", 5, None):
            self.assertEqual(u.call("PATCH", "/api/me", {"bg": bad})[0], 400, bad)
        self.assertEqual(u.call("PATCH", "/api/me", {"bg": ""})[0], 200)

    def test_photo_upload_is_private(self):
        u = self.c("saha1")
        me = u.boot()["me"]["id"]
        status, body = u.call("POST", "/api/me/background", raw=JPEG_GPS)
        self.assertEqual(status, 200, body)
        self.assertTrue(body["bg"].startswith("photo:"))
        status, data = u.call("GET", f"/files/bg/{me}")
        self.assertEqual(status, 200)
        self.assertNotIn(b"Exif", data[:4096])  # konum bilgisi dosyada kalmaz
        for other in ("saha2", "lider", "yonetici"):  # sahip dahil kimse başkasının resmini göremez
            self.assertEqual(self.c(other).call("GET", f"/files/bg/{me}")[0], 404, other)
        self.assertEqual(u.call("POST", "/api/me/background", raw=HEIC)[0], 415)
        self.assertEqual(u.call("POST", "/api/me/background", raw=b"")[0], 400)
        # palete geçince eski fotoğraf silinir
        u.call("PATCH", "/api/me", {"bg": "pal:ag"})
        self.assertEqual(u.call("GET", f"/files/bg/{me}")[0], 404)
        self.assertIsNone(images.background_path(os.path.join(self.cfg.data_dir, "backgrounds"), me))
        # PNG de olur; silme ucu seçimi sıfırlar
        self.assertEqual(u.call("POST", "/api/me/background", raw=PNG_1PX, ctype="image/png")[0], 200)
        self.assertEqual(u.call("DELETE", "/api/me/background")[0], 200)
        self.assertEqual(u.boot()["me"]["bg"], "")
        self.assertEqual(u.call("GET", f"/files/bg/{me}")[0], 404)

    # ---- sahibin kuralları ----
    def test_only_owner_sets_rules(self):
        for who in ("yonetici2", "lider", "saha1"):
            self.assertEqual(self.c(who).call("PATCH", "/api/settings", {"bg_choice": False})[0], 403, who)
        self.assertTrue(self.c("saha1").boot()["settings"]["bg_choice"])
        # yönetici otomasyon ayarını yine değiştirebilir
        self.assertEqual(self.c("yonetici2").call("PATCH", "/api/settings", {"auto_rule": True})[0], 200)

    def test_rules_lock_choice_and_upload(self):
        u = self.c("saha2")
        self.rules(bg_upload=False)
        self.assertEqual(u.call("POST", "/api/me/background", raw=JPEG_GPS)[0], 403)
        self.assertEqual(u.call("PATCH", "/api/me", {"bg": "pal:boya"})[0], 200)  # desen seçimi hâlâ serbest
        self.rules(bg_choice=False)
        self.assertEqual(u.call("PATCH", "/api/me", {"bg": "pal:yapi"})[0], 403)
        self.assertEqual(u.call("PATCH", "/api/me", {"bg": "none"})[0], 403)
        self.assertEqual(u.call("PATCH", "/api/me", {"bg": ""})[0], 200)  # mesleğe dönmek her zaman serbest
        self.rules(bg_choice=True, bg_upload=True, bg_enabled=False)
        self.assertFalse(u.boot()["settings"]["bg_enabled"])
        self.assertEqual(u.call("POST", "/api/me/background", raw=JPEG_GPS)[0], 403)

    def test_backup_contains_backgrounds(self):
        u = self.c("lider")
        self.assertEqual(u.call("POST", "/api/me/background", raw=JPEG_GPS)[0], 200)
        import io
        import zipfile
        status, data = self.c("yonetici").call("GET", "/api/backup")
        self.assertEqual(status, 200)
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            self.assertTrue(any(n.startswith("backgrounds/") for n in z.namelist()))
        u.call("DELETE", "/api/me/background")


if __name__ == "__main__":
    unittest.main()
