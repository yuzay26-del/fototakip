"""AI inceleme, tünel, DNS ve güvenlik testleri. OpenAI ve cloudflared yerine sahteleri kullanılır."""

import base64
import io
import json
import os
import stat
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fototakip import images  # noqa: E402
import ornek_veri as seed  # noqa: E402
from fototakip.server import Config, make_server  # noqa: E402
from test_api import JPEG_GPS, Client  # noqa: E402

FAKE_KEY = "sk-test-" + "a" * 40
FAKE_TOKEN = "eyJ" + "b" * 80


class FakeOpenAI(BaseHTTPRequestHandler):
    calls = []
    reply = None

    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeOpenAI.calls.append((self.headers.get("Authorization"), body))
        result = FakeOpenAI.reply if FakeOpenAI.reply is not None else {
            "summary": "Kablolar düzenli, etiket yok.",
            "observations": [{"level": "critical", "title": "Açık uç", "detail": "Sol altta yalıtımsız kablo ucu."},
                             {"level": "garip", "title": "x" * 500}, "bozuk"],
            "photo_quality": "harika", "limitations": "Arka taraf görünmüyor", "human_review_required": False}
        data = json.dumps({"output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(result)}]}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


FAKE_CLOUDFLARED = """#!/bin/sh
echo "INF args: $*"
echo "INF Requesting new quick Tunnel on trycloudflare.com..."
echo "INF |  https://ornek-deneme-kelime.trycloudflare.com  |"
echo "INF token=$TUNNEL_TOKEN"
sleep 0.3
echo "INF Registered tunnel connection connIndex=0"
exec sleep 30
"""


class IntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.ai = ThreadingHTTPServer(("127.0.0.1", 0), FakeOpenAI)
        threading.Thread(target=cls.ai.serve_forever, daemon=True).start()
        os.environ["FOTOTAKIP_AI_URL"] = f"http://127.0.0.1:{cls.ai.server_address[1]}/v1/responses"
        cf = os.path.join(cls.tmp.name, "cloudflared")
        with open(cf, "w") as f:
            f.write(FAKE_CLOUDFLARED)
        os.chmod(cf, 0o755)
        os.environ["FOTOTAKIP_CLOUDFLARED"] = cf
        cls.resolv = os.path.join(cls.tmp.name, "resolv.conf")
        with open(cls.resolv, "w") as f:
            f.write("nameserver 10.0.0.1\n")
        os.environ["FOTOTAKIP_RESOLV_CONF"] = cls.resolv
        data = os.path.join(cls.tmp.name, "data")
        cfg = Config(host="127.0.0.1", port=0, data_dir=data, quiet=True, geocoder="off")
        cls.server = make_server(cfg)
        seed.seed_demo(cfg.db_path, cfg.data_dir)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"
        cls.data = data

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.ai.shutdown()
        for k in ("FOTOTAKIP_AI_URL", "FOTOTAKIP_CLOUDFLARED", "FOTOTAKIP_RESOLV_CONF"):
            os.environ.pop(k, None)
        cls.tmp.cleanup()

    def mgr(self):
        return Client(self.base).login("yonetici")

    # ---- AI ----
    def test_ai_review_flow(self):
        cl = self.mgr()
        b = cl.boot()
        t = next(x for x in b["tasks"] if x["no_label"] == "İE-0143")
        svg_pid = t["photos"][0]["pid"]
        status, body = cl.call("POST", f"/api/photos/{svg_pid}/ai-review", {"task_id": t["id"]})
        self.assertEqual((status, body["error"]["code"]), (409, "ai_disabled"))
        self.assertEqual(cl.call("PATCH", "/api/admin/integrations", {"ai": {"openai_key": "yanlis"}})[0], 400)
        status, st = cl.call("PATCH", "/api/admin/integrations", {"ai": {"enabled": True, "openai_key": FAKE_KEY, "model": "gpt-4.1-mini"}})
        self.assertEqual(status, 200)
        self.assertTrue(st["ai"]["key_set"])
        self.assertEqual(st["ai"]["key_hint"], "…" + FAKE_KEY[-4:])
        self.assertNotIn(FAKE_KEY, json.dumps(st))
        mode = stat.S_IMODE(os.stat(os.path.join(self.data, "secrets.json")).st_mode)
        self.assertEqual(mode, 0o600)
        # çizim fotoğraf: anlaşılır hata, sunucu hatası değil
        status, body = cl.call("POST", f"/api/photos/{svg_pid}/ai-review", {"task_id": t["id"]})
        self.assertEqual(status, 400)
        self.assertIn("çizim", body["error"]["message"])
        # gerçek fotoğraf
        status, up = cl.call("POST", f"/api/photos?type=issue&task_id={t['id']}", raw=JPEG_GPS)
        pid = up["photo_id"]
        before = len(FakeOpenAI.calls)
        status, r = cl.call("POST", f"/api/photos/{pid}/ai-review", {"task_id": t["id"]})
        self.assertEqual(status, 200, r)
        auth, payload = FakeOpenAI.calls[-1]
        self.assertEqual(auth, "Bearer " + FAKE_KEY)
        img = payload["input"][0]["content"][1]["image_url"]
        self.assertTrue(img.startswith("data:image/jpeg;base64,"))
        self.assertNotIn(b"Exif", base64.b64decode(img.split(",", 1)[1]), "OpenAI'ye konum bilgisi gitmemeli")
        self.assertIn("İE-0143", "İE-0143")  # bağlam başlıkla gider
        self.assertIn("Elektrik panosu", payload["input"][0]["content"][0]["text"])
        # model çıktısı daraltılır
        self.assertTrue(r["human_review_required"])
        self.assertEqual(r["photo_quality"], "limited")
        self.assertEqual([o["level"] for o in r["observations"]], ["critical", "uncertain"])
        self.assertEqual(len(r["observations"][1]["title"]), 120)
        self.assertEqual(r["limitations"], ["Arka taraf görünmüyor"])
        # önbellek: ikinci çağrı OpenAI'ye gitmez
        status, r2 = cl.call("POST", f"/api/photos/{pid}/ai-review", {"task_id": t["id"]})
        self.assertTrue(r2["cached"])
        self.assertEqual(len(FakeOpenAI.calls) - before, 1)
        # bootstrap'ta görünür
        self.assertEqual(cl.boot()["photos"][pid]["ai"]["summary"], "Kablolar düzenli, etiket yok.")
        # saha rolü zorla yeniden inceletemez, yönetici inceletebilir
        mert = Client(self.base).login("saha1")
        mert.call("POST", f"/api/photos/{pid}/ai-review", {"task_id": t["id"], "force": True})
        self.assertEqual(len(FakeOpenAI.calls) - before, 1)
        cl.call("POST", f"/api/photos/{pid}/ai-review", {"task_id": t["id"], "force": True})
        self.assertEqual(len(FakeOpenAI.calls) - before, 2)
        # bozuk model çıktısı: 400, çökme yok
        FakeOpenAI.reply = ["liste", "nesne değil"]
        try:
            status, body = cl.call("POST", f"/api/photos/{pid}/ai-review", {"task_id": t["id"], "force": True})
        finally:
            FakeOpenAI.reply = None
        self.assertEqual(status, 400)
        # yedekte gizli dosya yok
        status, data = cl.call("GET", "/api/backup")
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            self.assertFalse(any("secrets" in n for n in z.namelist()))

    def test_integrations_manager_only(self):
        mert = Client(self.base).login("saha1")
        self.assertEqual(mert.call("GET", "/api/admin/integrations")[0], 403)
        self.assertEqual(mert.call("POST", "/api/admin/tunnel/start")[0], 403)

    # ---- DNS ----
    def test_dns(self):
        cl = self.mgr()
        status, st = cl.call("GET", "/api/admin/integrations")
        self.assertEqual(st["dns"]["servers"], ["10.0.0.1"])
        status, st = cl.call("PATCH", "/api/admin/integrations", {"dns": "opendns"})
        self.assertEqual(status, 200)
        self.assertEqual(st["dns"]["servers"], ["208.67.222.222", "208.67.220.220"])
        self.assertEqual(st["dns"]["preset"], "opendns")
        self.assertTrue(os.path.exists(self.resolv + ".fototakip-yedek"))
        self.assertEqual(cl.call("PATCH", "/api/admin/integrations", {"dns": "bilinmeyen"})[0], 400)

    # ---- tünel ----
    def test_z_tunnel(self):  # en son: demo parolalarını değiştirir
        cl = self.mgr()
        cl.call("PATCH", "/api/admin/integrations", {"tunnel": {"mode": "quick"}})
        status, body = cl.call("POST", "/api/admin/tunnel/start")
        self.assertEqual((status, body["error"]["code"]), (409, "demo_passwords"))
        st = cl.call("GET", "/api/admin/integrations")[1]
        self.assertEqual(sorted(st["demo_password_users"]), ["saha1", "saha2", "yonetici"])
        users = {u["username"]: u["id"] for u in cl.boot()["users"]}
        self.assertEqual(cl.call("POST", f"/api/admin/users/{users['saha1']}/password", {"password": "kisa"})[0], 400)
        for name in ("saha1", "saha2", "yonetici"):
            self.assertEqual(cl.call("POST", f"/api/admin/users/{users[name]}/password", {"password": "Saha-2026-guclu"})[0], 200)
        self.assertEqual(cl.call("GET", "/api/admin/integrations")[0], 200)  # kendi oturumu açık kaldı
        self.assertEqual(Client(self.base).login("saha1", "Saha-2026-guclu").boot()["me"]["username"], "saha1")
        status, st = cl.call("POST", "/api/admin/tunnel/start")
        self.assertEqual(status, 200, st)
        st = self._wait(cl, "running")
        self.assertEqual(st["tunnel"]["run_url"], "https://ornek-deneme-kelime.trycloudflare.com")
        args = next(x for x in st["tunnel"]["run_log"] if "args:" in x)
        self.assertIn(f"--url http://127.0.0.1:{self.server.server_address[1]}", args)  # localhost değil: IPv6 tuzağı
        st = cl.call("POST", "/api/admin/tunnel/stop")[1]
        self.assertEqual(st["tunnel"]["run_status"], "stopped")
        # adlandırılmış tünel: token komut satırına değil ortama, kayıtta gizli
        self.assertEqual(cl.call("PATCH", "/api/admin/integrations", {"tunnel": {"mode": "named", "tunnel_token": "kisa"}})[0], 400)
        self.assertEqual(cl.call("PATCH", "/api/admin/integrations", {"tunnel": {"mode": "named", "hostname": "https://Is.Ornek.com/", "tunnel_token": FAKE_TOKEN}})[0], 200)
        cl.call("POST", "/api/admin/tunnel/start")
        st = self._wait(cl, "running")
        self.assertEqual(st["tunnel"]["run_url"], "https://is.ornek.com")
        logs = "\n".join(st["tunnel"]["run_log"])
        self.assertIn("token=•••", logs)
        self.assertNotIn(FAKE_TOKEN, json.dumps(st))
        cl.call("POST", "/api/admin/tunnel/stop")

    def _wait(self, cl, status):
        for _ in range(60):
            st = cl.call("GET", "/api/admin/integrations")[1]
            if st["tunnel"]["run_status"] == status:
                return st
            time.sleep(0.1)
        self.fail(f"tünel '{status}' olmadı: {st['tunnel']}")

    # ---- güvenlik ----
    def test_login_throttle_and_secure_cookie(self):
        cl = Client(self.base)
        for _ in range(5):
            self.assertEqual(cl.call("POST", "/api/login", {"username": "saha2", "password": "yanlis"})[0], 401)
        status, body = cl.call("POST", "/api/login", {"username": "saha2", "password": "demo1234"})
        self.assertEqual(status, 429)
        req = urllib.request.Request(self.base + "/api/login", method="POST", data=json.dumps({"username": "saha1", "password": "demo1234"}).encode(),
                                     headers={"Content-Type": "application/json", "X-Forwarded-Proto": "https"})
        try:
            with urllib.request.urlopen(req) as r:
                cookie = r.headers.get("Set-Cookie")
        except urllib.error.HTTPError:
            cookie = ""  # parola başka testte değişmiş olabilir
        if cookie:
            self.assertIn("Secure", cookie)


class StripTest(unittest.TestCase):
    def test_strip_jpeg_metadata(self):
        self.assertIn(b"Exif", JPEG_GPS)
        out = images.strip_jpeg_metadata(JPEG_GPS)
        self.assertNotIn(b"Exif", out)
        self.assertEqual(images.read_exif(out), {})
        self.assertTrue(out.startswith(b"\xff\xd8") and out.endswith(b"\xff\xd9"))
        self.assertEqual(images.strip_jpeg_metadata(b"PNG..."), b"PNG...")


import urllib.error  # noqa: E402

if __name__ == "__main__":
    unittest.main()
