"""İlk kurulum testleri: boş veritabanı, kurulum kodu, ilk yönetici."""

import os
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fototakip import api, db  # noqa: E402
from fototakip.server import Config, make_server  # noqa: E402
from test_api import Client  # noqa: E402


class SetupTest(unittest.TestCase):
    def setUp(self):
        api._FAILS.clear()  # giriş deneme sayacı modül genelinde; önceki testlerden kalmasın
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = Config(host="127.0.0.1", port=0, data_dir=self.tmp.name, quiet=True, geocoder="off")
        self.server = make_server(self.cfg)
        con = db.connect(self.cfg.db_path)
        self.code = api.new_setup_code(con)
        con.close()
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.c = Client(f"http://127.0.0.1:{self.server.server_address[1]}")

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.tmp.cleanup()

    def form(self, **kw):
        body = {"code": self.code, "name": "Ekip Lideri", "username": "lider", "password": "uzun-parola-1"}
        body.update(kw)
        return self.c.call("POST", "/api/setup", body)

    def test_empty_install_has_no_accounts(self):
        st, h = self.c.call("GET", "/api/health")
        self.assertTrue(h["needs_setup"])
        for user in ("yonetici", "admin", "saha1", "saha2"):
            st, _ = self.c.call("POST", "/api/login", {"username": user, "password": "demo1234"})
            self.assertEqual(st, 401, user)
        con = db.connect(self.cfg.db_path)
        counts = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("users", "projects", "tasks", "photos")}
        con.close()
        self.assertEqual(counts, {"users": 0, "projects": 0, "tasks": 0, "photos": 0})

    def test_setup_creates_manager_once(self):
        st, body = self.form(code=self.code.lower().replace("-", " "))  # büyük/küçük harf, tire, boşluk fark etmez
        self.assertEqual(st, 200, body)
        self.assertEqual(body["user"]["role"], "owner")
        self.c.token = body["token"]
        self.assertEqual(self.c.boot()["me"]["username"], "lider")
        self.assertFalse(self.c.call("GET", "/api/health")[1]["needs_setup"])
        st, body = self.form(username="ikinci")
        self.assertEqual((st, body["error"]["code"]), (409, "already_setup"))
        con = db.connect(self.cfg.db_path)
        self.assertEqual(db.setting(con, "setup_code", ""), "")  # kod tek kullanımlık
        con.close()

    def test_validation(self):
        self.assertEqual(self.form(password="kisa")[1]["error"]["code"], "weak_password")
        self.assertEqual(self.form(password="demo1234")[1]["error"]["code"], "weak_password")
        self.assertEqual(self.form(username="Büyük Ad")[1]["error"]["code"], "bad_username")
        self.assertEqual(self.form(name="")[0], 400)
        self.assertTrue(self.c.call("GET", "/api/health")[1]["needs_setup"])

    def test_wrong_code_locks_after_five(self):
        for i in range(api.SETUP_MAX_FAILS):
            st, body = self.form(code="AAAA-AAAA")
            self.assertEqual(st, 403, i)
        st, body = self.form()  # doğru kod da artık geçmez
        self.assertEqual((st, body["error"]["code"]), (423, "setup_locked"))


if __name__ == "__main__":
    unittest.main()
