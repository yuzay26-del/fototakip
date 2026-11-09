"""Yetki hiyerarşisi ve izolasyon testleri: sahip > yönetici > ekip lideri > teknisyen."""

import os
import sqlite3
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fototakip import api, auth, db, perms  # noqa: E402
from fototakip.server import Config, make_server  # noqa: E402
import ornek_veri as seed  # noqa: E402
from test_api import JPEG_GPS, Client  # noqa: E402

PW = {"lider": seed.STRONG_PASSWORD, "yonetici2": seed.STRONG_PASSWORD}


class YetkiTest(unittest.TestCase):
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

    def uid(self, username):
        return next(u["id"] for u in self.c("yonetici").boot()["users"] if u.get("username") == username)

    # ---- görünürlük ----
    def test_field_isolation_everywhere(self):
        own, other = self.c("saha1"), self.c("saha2")
        mine, theirs = own.boot(), other.boot()
        mine_ids = {t["id"] for t in mine["tasks"]}
        their_only = [t for t in theirs["tasks"] if t["id"] not in mine_ids]
        self.assertTrue(their_only)
        t = their_only[0]
        # ayrıntı, yazma, yorum, imza dosyası, arama
        self.assertEqual(own.call("PATCH", f"/api/tasks/{t['id']}", {"title": "x"})[0], 404)
        self.assertEqual(own.call("POST", f"/api/tasks/{t['id']}/comments", {"text": "x"})[0], 404)
        self.assertEqual(own.call("GET", f"/files/signature/{t['id']}")[0], 404)
        if t["photos"]:
            self.assertEqual(own.call("GET", f"/files/{t['photos'][0]['pid']}")[0], 404)
        ids = own.call("GET", "/api/search?q=%C4%B0E-")[1]["ids"]
        self.assertTrue(set(ids) <= mine_ids)
        # müşteriler: yalnızca kendi işlerinin müşterileri
        self.assertEqual({p["id"] for p in mine["projects"]}, {x["project_id"] for x in mine["tasks"]})
        # kişiler: kullanıcı adı, telefon, yetenek gibi ayrıntılar başkaları için gizli
        for u in mine["users"]:
            if u["id"] != mine["me"]["id"]:
                self.assertNotIn("username", u)
        self.assertNotIn("yonetici2", [u.get("username") for u in mine["users"]])
        # başka bir müşteride iş açamaz
        foreign = [p for p in theirs["projects"] if p["id"] not in {x["id"] for x in mine["projects"]}]
        if foreign:
            st, body = own.call("POST", "/api/tasks", {"project_id": foreign[0]["id"], "title": "x"})
            self.assertEqual((st, body["error"]["code"]), (400, "bad_project"))

    def test_field_permissions(self):
        cl = self.c("saha1")
        me = cl.boot()["me"]
        self.assertEqual(me["perms"], {"admin": False, "owner": False, "lead": False, "customers": False, "roles": []})
        self.assertEqual(cl.call("POST", "/api/users", {"username": "x1", "name": "X", "password": "uzun-parola"})[0], 403)
        self.assertEqual(cl.call("POST", "/api/projects", {"name": "Yeni"})[0], 403)
        self.assertEqual(cl.call("POST", "/api/skills", {"name": "Çatı"})[0], 403)
        self.assertEqual(cl.call("GET", "/api/admin/integrations")[0], 403)
        self.assertEqual(cl.call("GET", "/api/backup")[0], 403)
        # kendi işini başkasına atayamaz, yeteneği değiştiremez, tamamlayamaz
        t = cl.boot()["tasks"][0]
        self.assertEqual(cl.call("PATCH", f"/api/tasks/{t['id']}", {"assignee_id": self.uid("saha2")})[0], 403)
        self.assertEqual(cl.call("PATCH", f"/api/tasks/{t['id']}", {"skill_id": "sk_boya"})[0], 403)
        self.assertEqual(cl.call("PATCH", f"/api/tasks/{t['id']}", {"status": "done"})[0], 403)

    def test_lead_sees_team_and_pool(self):
        mgr, lead = self.c("yonetici").boot(), self.c("lider")
        lb = lead.boot()
        team = {u["id"] for u in mgr["users"] if u.get("username") in ("lider", "saha1")}
        expected = {t["id"] for t in mgr["tasks"] if t["assignee_id"] is None or t["assignee_id"] in team}
        self.assertEqual({t["id"] for t in lb["tasks"]}, expected)
        self.assertEqual(len(lb["projects"]), len(mgr["projects"]))  # müşteri rehberi ortak
        self.assertTrue(lb["me"]["perms"]["customers"])
        saha1 = next(u for u in lb["users"] if u["id"] in team and u["role"] == "field")
        self.assertIn("phone", saha1)  # ekip üyesinin iletişim bilgisi
        saha2 = next((u for u in lb["users"] if u["name"] == "Saha İki"), None)
        self.assertTrue(saha2 is None or "phone" not in saha2)

    def test_lead_assigns_and_reviews_only_team(self):
        lead = self.c("lider")
        mgr = self.c("yonetici")
        p = mgr.boot()["projects"][0]
        st, r = lead.call("POST", "/api/tasks", {"project_id": p["id"], "title": "Lider işi", "skill_id": "sk_elektrik",
                                                 "assignee_id": self.uid("saha1")})
        self.assertEqual(st, 200, r)
        st, body = lead.call("PATCH", f"/api/tasks/{r['id']}", {"assignee_id": self.uid("saha2")})
        self.assertEqual(st, 403)
        self.assertEqual(lead.call("PATCH", f"/api/tasks/{r['id']}", {"status": "review"})[0], 200)
        self.assertEqual(lead.call("POST", f"/api/tasks/{r['id']}/review", {"decision": "approve"})[0], 200)
        # ekip dışına atanmış iş görünmez
        other = next(t for t in mgr.boot()["tasks"] if t["assignee_id"] == self.uid("saha2"))
        self.assertEqual(lead.call("POST", f"/api/tasks/{other['id']}/review", {"decision": "approve"})[0], 404)
        # müşteri ekler ama silemez, kişi ekleyemez
        st, np = lead.call("POST", "/api/projects", {"name": "Lider müşterisi", "phone": "0212 555 01 01"})
        self.assertEqual(st, 200)
        self.assertEqual(lead.call("DELETE", f"/api/projects/{np['id']}")[0], 403)
        self.assertEqual(lead.call("POST", "/api/users", {"username": "x2", "name": "X", "password": "uzun-parola"})[0], 403)

    def test_manager_limits(self):
        m2 = self.c("yonetici2")
        self.assertEqual(m2.boot()["me"]["perms"]["roles"], ["lead", "field"])
        self.assertEqual(m2.call("POST", "/api/users", {"username": "sahip2", "name": "S", "password": "uzun-parola-1", "role": "owner"})[0], 403)
        self.assertEqual(m2.call("PATCH", f"/api/users/{self.uid('yonetici')}", {"name": "Değişti"})[0], 403)
        self.assertEqual(m2.call("POST", f"/api/admin/users/{self.uid('yonetici')}/password", {"password": "uzun-parola-1"})[0], 403)
        self.assertEqual(m2.call("GET", "/api/admin/integrations")[0], 403)  # bağlantılar yalnızca sahip
        self.assertEqual(m2.call("GET", "/api/backup")[0], 403)
        st, r = m2.call("POST", "/api/users", {"username": "yeni.tekn", "name": "Yeni Teknisyen", "password": "uzun-parola-1",
                                               "role": "field", "lead_id": self.uid("lider"), "skills": ["sk_klima"], "phone": "0212 555 02 02"})
        self.assertEqual(st, 200, r)
        u = next(x for x in m2.boot()["users"] if x["id"] == r["id"])
        self.assertEqual((u["lead_id"], u["skills"], u["phone"]), (self.uid("lider"), ["sk_klima"], "0212 555 02 02"))
        # lider olmayan birini lider seçemez
        self.assertEqual(m2.call("PATCH", f"/api/users/{r['id']}", {"lead_id": self.uid("saha2")})[0], 400)

    def test_deactivate_and_sessions(self):
        owner = self.c("yonetici")
        st, r = owner.call("POST", "/api/users", {"username": "gecici", "name": "Geçici Kişi", "password": "uzun-parola-1"})
        self.assertEqual(st, 200)
        tmp = Client(self.base).login("gecici", "uzun-parola-1")
        self.assertEqual(owner.call("PATCH", f"/api/users/{r['id']}", {"active": False})[0], 200)
        self.assertEqual(tmp.call("GET", "/api/bootstrap")[0], 401)  # oturum kapandı
        st, body = Client(self.base).call("POST", "/api/login", {"username": "gecici", "password": "uzun-parola-1"})
        self.assertEqual((st, body["error"]["code"]), (403, "account_disabled"))
        self.assertEqual(owner.call("PATCH", f"/api/users/{r['id']}", {"active": True})[0], 200)
        tmp = Client(self.base).login("gecici", "uzun-parola-1")
        self.assertEqual(owner.call("PATCH", f"/api/users/{r['id']}", {"revoke_sessions": True})[0], 200)
        self.assertEqual(tmp.call("GET", "/api/bootstrap")[0], 401)
        # pasif kişiye iş atanamaz
        owner.call("PATCH", f"/api/users/{r['id']}", {"active": False})
        t = owner.boot()["tasks"][0]
        self.assertEqual(owner.call("PATCH", f"/api/tasks/{t['id']}", {"assignee_id": r["id"]})[0], 403)

    def test_last_owner_and_self(self):
        owner = self.c("yonetici")
        me = owner.boot()["me"]["id"]
        self.assertEqual(owner.call("PATCH", f"/api/users/{me}", {"role": "field"})[0], 403)  # kendini düzenleyemez

    def test_lead_role_change_dissolves_team(self):
        owner = self.c("yonetici")
        st, r = owner.call("POST", "/api/users", {"username": "lider2", "name": "Lider İki", "password": "uzun-parola-1", "role": "lead"})
        st, f = owner.call("POST", "/api/users", {"username": "tekn2", "name": "Teknisyen İki", "password": "uzun-parola-1", "lead_id": r["id"]})
        self.assertEqual(owner.call("PATCH", f"/api/users/{r['id']}", {"role": "field"})[0], 200)
        u = next(x for x in owner.boot()["users"] if x["id"] == f["id"])
        self.assertIsNone(u["lead_id"])

    def test_skills_crud(self):
        owner = self.c("yonetici")
        st, r = owner.call("POST", "/api/skills", {"name": "Güneş paneli", "icon": "sun", "color": "#EAB308"})
        self.assertEqual(st, 200)
        self.assertEqual(owner.call("POST", "/api/skills", {"name": "güneş PANELİ"})[0], 409)
        self.assertEqual(owner.call("POST", "/api/skills", {"name": "Kötü", "icon": "<svg>"})[0], 400)
        self.assertEqual(owner.call("PATCH", f"/api/skills/{r['id']}", {"color": "kırmızı"})[0], 400)
        self.assertEqual(owner.call("PATCH", f"/api/skills/{r['id']}", {"color": "#16a34a"})[0], 200)
        sk = next(s for s in owner.boot()["skills"] if s["id"] == r["id"])
        self.assertEqual(sk["color"], "#16A34A")
        self.assertEqual(owner.call("DELETE", f"/api/skills/{r['id']}")[0], 200)

    def test_customer_fields_and_delete(self):
        owner = self.c("yonetici")
        st, r = owner.call("POST", "/api/projects", {"name": "Yeni Müşteri", "phone": "0212 555 03 03", "email": "a@b.co", "notes": "Kapı kodu yok"})
        self.assertEqual(owner.call("PATCH", f"/api/projects/{r['id']}", {"archived": True})[0], 200)
        p = next(x for x in owner.boot()["projects"] if x["id"] == r["id"])
        self.assertEqual((p["phone"], p["email"], p["archived"]), ("0212 555 03 03", "a@b.co", 1))
        self.assertEqual(owner.call("DELETE", f"/api/projects/{r['id']}")[0], 200)
        busy = owner.boot()["tasks"][0]["project_id"]
        self.assertEqual(owner.call("DELETE", f"/api/projects/{busy}")[1]["error"]["code"], "has_tasks")

    def test_theme_preference(self):
        cl = self.c("saha2")
        self.assertEqual(cl.call("PATCH", "/api/me", {"theme": "saha"})[0], 200)
        self.assertEqual(cl.boot()["me"]["theme"], "saha")
        self.assertEqual(cl.call("PATCH", "/api/me", {"theme": "neon"})[0], 400)

    def test_field_new_task_from_photo_on_own_customer(self):
        cl = self.c("saha1")
        p = cl.boot()["projects"][0]
        st, r = cl.call("POST", f"/api/photos?type=before&new_task=1&project_id={p['id']}", raw=JPEG_GPS)
        self.assertEqual(st, 200, r)
        t = next(x for x in cl.boot()["tasks"] if x["id"] == r["task_id"])
        self.assertEqual(t["assignee_id"], cl.boot()["me"]["id"])

    def test_event_filter(self):
        con = db.connect(self.cfg.db_path)
        try:
            users = {r["username"]: dict(r) for r in con.execute("SELECT * FROM users")}
            other = con.execute("SELECT id FROM tasks WHERE assignee_id = ?", (users["saha2"]["id"],)).fetchone()["id"]
            ev = {"type": "task", "id": other, "by": users["saha2"]["id"]}
            self.assertEqual(perms.event_for(con, users["saha1"], ev), {"type": "refresh"})
            self.assertEqual(perms.event_for(con, users["saha2"], ev), ev)
            self.assertEqual(perms.event_for(con, users["yonetici"], ev), ev)
        finally:
            con.close()


class MigrationTest(unittest.TestCase):
    def test_v3_to_v4_keeps_data(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "eski.db")
            con = sqlite3.connect(path)
            con.executescript(db.SCHEMA)
            for v in (2, 3):
                for stmt in [x for x in db.MIGRATIONS[v].split(";") if x.strip()]:
                    con.execute(stmt)
            con.execute("PRAGMA user_version = 3")
            pw = auth.hash_password("eski-parola-1")
            con.execute("INSERT INTO users VALUES ('m1','patron','Patron','PA','manager',?, '2026-01-01')", (pw,))
            con.execute("INSERT INTO users VALUES ('m2','ikinci','İkinci','İK','manager',?, '2026-02-01')", (pw,))
            con.execute("INSERT INTO users VALUES ('f1','tekn','Tekn','TE','field',?, '2026-03-01')", (pw,))
            con.execute("INSERT INTO sessions VALUES ('tok','f1','2026-01-01','2999-01-01')")
            con.execute("INSERT INTO projects(id,name,short,created_at) VALUES ('p1','Müşteri','M','2026-01-01')")
            con.execute("INSERT INTO tasks(id,no,project_id,title,status,assignee_id,due,created_by,created_at,updated_at) "
                        "VALUES ('t1',1,'p1','İş','open','f1','2026-01-05','m1','2026-01-01','2026-01-01')")
            con.commit()
            con.close()
            db.init(path)
            con = db.connect(path)
            roles = {r["username"]: r["role"] for r in con.execute("SELECT * FROM users")}
            self.assertEqual(roles, {"patron": "owner", "ikinci": "manager", "tekn": "field"})
            self.assertEqual(con.execute("SELECT user_id FROM sessions").fetchone()[0], "f1")  # oturum silinmedi
            self.assertEqual(con.execute("SELECT assignee_id FROM tasks").fetchone()[0], "f1")
            self.assertEqual(con.execute("SELECT COUNT(*) FROM skills").fetchone()[0], 6)
            self.assertEqual(con.execute("PRAGMA user_version").fetchone()[0], db.SCHEMA_VERSION)
            self.assertEqual(con.execute("PRAGMA foreign_keys").fetchone()[0], 1)
            con.close()


if __name__ == "__main__":
    unittest.main()
