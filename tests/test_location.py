"""Konum, adres bulma ve müşteri haritası testleri. Gerçek Nominatim yerine sahte sunucu kullanılır."""

import json
import os
import sqlite3
import sys
import tempfile
import threading
import unittest
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fototakip import db, geo, seed  # noqa: E402
from fototakip.server import Config, make_server  # noqa: E402
from test_api import JPEG_A, JPEG_B, JPEG_GPS, Client  # noqa: E402


class FakeNominatim(BaseHTTPRequestHandler):
    calls = []

    def log_message(self, *a):
        pass

    def do_GET(self):
        q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(self.path).query))
        FakeNominatim.calls.append((q, self.headers.get("User-Agent", "")))
        lat = float(q["lat"])
        body = {"address": {"neighbourhood": "Kuzguncuk Mahallesi", "road": "İcadiye Caddesi", "house_number": "41",
                            "town": "Üsküdar", "province": "İstanbul"}} if lat > 41 else \
               {"address": {"suburb": "Caferağa Mahallesi", "road": "Moda Caddesi", "house_number": "120",
                            "city_district": "Kadıköy", "city": "İstanbul"}}
        data = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class LocationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fake = ThreadingHTTPServer(("127.0.0.1", 0), FakeNominatim)
        threading.Thread(target=cls.fake.serve_forever, daemon=True).start()
        cls.tmp = tempfile.TemporaryDirectory()
        cfg = Config(host="127.0.0.1", port=0, data_dir=cls.tmp.name, quiet=True,
                     geocoder=f"http://127.0.0.1:{cls.fake.server_address[1]}/reverse")
        cls.server = make_server(cfg)
        seed.seed_demo(cfg.db_path, cfg.data_dir)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.fake.shutdown()
        cls.tmp.cleanup()

    def mgr(self):
        return Client(self.base).login("yusuf")

    def proj(self, cl, pid):
        return next(p for p in cl.boot()["projects"] if p["id"] == pid)

    def test_new_customer_gets_location_and_address_from_photo(self):
        cl = self.mgr()
        _, r = cl.call("POST", "/api/projects", {"name": "Kuzguncuk · Dükkan", "client": "Bora Kaya"})
        pid = r["id"]
        p = self.proj(cl, pid)
        self.assertIsNone(p["lat"])
        self.assertEqual(p["location_source"], "none")
        status, up = cl.call("POST", f"/api/photos?type=before&new_task=1&project_id={pid}&lat=41.03050&lng=29.04400&acc=8", raw=JPEG_A)
        self.assertEqual(status, 200, up)
        self.assertIsNone(up["warning"])
        self.assertTrue(self.server.geo.drain())
        p = self.proj(cl, pid)
        self.assertAlmostEqual(p["lat"], 41.0305, places=4)
        self.assertEqual(p["location_source"], "photo")
        self.assertEqual(p["address"], "Kuzguncuk Mahallesi, İcadiye Caddesi No 41, Üsküdar/İstanbul")
        self.assertEqual(p["address_source"], "photo")
        ph = cl.boot()["photos"][up["photo_id"]]
        self.assertEqual(ph["gps_source"], "device")
        self.assertEqual(ph["gps_accuracy"], 8)
        self.assertEqual(ph["address"], p["address"])
        self.assertTrue(any("FotoTakip/" in ua for _, ua in FakeNominatim.calls))

    def test_far_photo_warns(self):
        cl = self.mgr()
        b = cl.boot()
        t = next(t for t in b["tasks"] if t["no_label"] == "İE-0143")  # Ataşehir
        status, up = cl.call("POST", f"/api/photos?type=progress&task_id={t['id']}&lat=40.9862&lng=29.0270", raw=JPEG_B)
        self.assertEqual(status, 200)
        self.assertIn("uzakta", up["warning"])
        log = [a["text"] for a in next(x for x in cl.boot()["tasks"] if x["id"] == t["id"])["activity"]]
        self.assertTrue(any("uzakta" in x for x in log))

    def test_suggestion_apply_and_exif_priority(self):
        cl = self.mgr()
        b = cl.boot()
        moda = next(p for p in b["projects"] if p["short"] == "Kadıköy")
        t = next(t for t in b["tasks"] if t["no_label"] == "İE-0150")
        # EXIF'te GPS var (40.9862, 29.0270): cihaz konumu verilse de EXIF önce gelir
        status, up = cl.call("POST", f"/api/photos?type=before&task_id={t['id']}&lat=10&lng=10", raw=JPEG_GPS)
        self.assertEqual(status, 200)
        self.assertEqual(cl.boot()["photos"][up["photo_id"]]["gps_source"], "exif")
        self.assertTrue(self.server.geo.drain())
        p = self.proj(cl, moda["id"])
        self.assertEqual(p["address"], "Caferağa Mah., Moda Cd. 112")  # elle girilen adres korunur
        self.assertEqual(p["suggested_address"], "Caferağa Mahallesi, Moda Caddesi No 120, Kadıköy/İstanbul")
        self.assertEqual(cl.call("PATCH", f"/api/projects/{moda['id']}", {"apply_suggestion": True})[0], 200)
        p = self.proj(cl, moda["id"])
        self.assertEqual(p["address"], "Caferağa Mahallesi, Moda Caddesi No 120, Kadıköy/İstanbul")
        self.assertEqual(p["address_source"], "photo")
        self.assertIsNone(p["suggested_address"])
        self.assertEqual(cl.call("PATCH", f"/api/projects/{moda['id']}", {"apply_suggestion": True})[0], 409)

    def test_geocode_endpoint_and_cache(self):
        cl = self.mgr()
        before = len(FakeNominatim.calls)
        s1, r1 = cl.call("GET", "/api/geocode?lat=41.04&lng=29.05")
        s2, r2 = cl.call("GET", "/api/geocode?lat=41.04001&lng=29.05001")  # aynı 11 m hücre
        self.assertEqual((s1, s2), (200, 200))
        self.assertEqual(r1, r2)
        self.assertEqual(len(FakeNominatim.calls) - before, 1)
        self.assertEqual(cl.call("GET", "/api/geocode?lat=abc&lng=1")[0], 400)

    def test_project_patch_location(self):
        cl = self.mgr()
        b = cl.boot()
        p = next(p for p in b["projects"] if p["short"] == "Maltepe")
        self.assertEqual(Client(self.base).login("mert").call("PATCH", f"/api/projects/{p['id']}", {"lat": 1, "lng": 1})[0], 403)
        self.assertEqual(cl.call("PATCH", f"/api/projects/{p['id']}", {"lat": 40.95, "lng": 29.15, "location_source": "map"})[0], 200)
        p2 = self.proj(cl, p["id"])
        self.assertEqual((p2["lat"], p2["location_source"]), (40.95, "map"))
        self.assertEqual(cl.call("PATCH", f"/api/projects/{p['id']}", {"lat": 40.95})[0], 400)


class GeoUnitTest(unittest.TestCase):
    def test_distance_and_format(self):
        self.assertAlmostEqual(geo.distance_m(41.0, 29.0, 41.0, 29.01), 839, delta=5)
        self.assertEqual(geo.fmt_distance(2340), "2,3 km")
        self.assertEqual(geo.format_address({"display_name": "A, B, C, D, E"}), "A, B, C, D")
        self.assertIsNone(geo.format_address({}))

    def test_migration_v1_to_v2_keeps_data(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "old.db")
            con = sqlite3.connect(path)
            con.executescript(db.SCHEMA)
            con.execute("PRAGMA user_version = 1")
            con.execute("INSERT INTO projects(id, name, short, created_at) VALUES ('p', 'Eski', 'E', 'x')")
            con.commit()
            con.close()
            db.init(path)
            con = db.connect(path)
            self.assertEqual(con.execute("PRAGMA user_version").fetchone()[0], db.SCHEMA_VERSION)
            row = con.execute("SELECT name, location_source, address_source FROM projects").fetchone()
            self.assertEqual(tuple(row), ("Eski", "none", "none"))
            con.execute("SELECT key FROM geocode_cache").fetchall()
            con.close()

    def test_disabled_geocoder(self):
        g = geo.Geocoder(":memory:", "off")
        self.assertFalse(g.enabled)
        g.stop()


if __name__ == "__main__":
    unittest.main()
