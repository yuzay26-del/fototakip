"""Yalnızca testler için örnek veri: 3 kişi, 4 müşteri, 10 iş, çizim fotoğraflar.

Uygulama bu veriyi yüklemez. Adlar ve iletişim bilgileri uydurmadır.
"""

from __future__ import annotations

import hashlib
import os
from datetime import date, datetime, timedelta, timezone

from fototakip import auth, db

DEMO_PASSWORD = "demo1234"
HERE = os.path.dirname(os.path.abspath(__file__))


def _ts(days: int, h: int, m: int) -> str:
    t = datetime.now().replace(hour=h, minute=m, second=0, microsecond=0) + timedelta(days=days)
    return t.astimezone(timezone.utc).isoformat(timespec="seconds")


def _day(n: int) -> str:
    return (date.today() + timedelta(days=n)).isoformat()




def seed_demo(path: str, data_dir: str) -> None:
    con = db.connect(path)
    photos_dir = os.path.join(data_dir, "photos")
    os.makedirs(photos_dir, exist_ok=True)
    try:
        with db.tx(con):
            users = {
                "u1": ("yonetici", "Deneme Yönetici", "DY", "manager"),
                "u2": ("saha1", "Saha Bir", "SB", "field"),
                "u3": ("saha2", "Saha İki", "Sİ", "field"),
            }
            uid = {}
            pw = auth.hash_password(DEMO_PASSWORD)
            for key, (username, name, short, role) in users.items():
                uid[key] = db.new_id()
                con.execute("INSERT INTO users(id, username, name, short, role, pw_hash, created_at) VALUES (?,?,?,?,?,?,?)",
                            (uid[key], username, name, short, role, pw, db.now()))

            projects = {
                "p1": ("Kadıköy · Moda Apt.", "Kadıköy", "Moda Apt. Yönetimi", "Site yöneticisi", "Caferağa Mah., Moda Cd. 112", 40.9862, 29.0270),
                "p2": ("Ataşehir · Plaza Ofis", "Ataşehir", "Nova Danışmanlık", "Ofis yöneticisi", "Barbaros Mah., Halk Cd. 8, Kat 3", 40.9923, 29.1244),
                "p3": ("Maltepe · Depo", "Maltepe", "Kuzey Lojistik", "Depo sorumlusu", "Esenkent Mah., Depo Sk. 4", 40.9480, 29.1490),
                "p4": ("Üsküdar · Kuzguncuk Ev", "Kuzguncuk", "Kuzguncuk Ev", "Ev sahibi", "", None, None),
            }
            pid = {}
            for key, (name, short, client, contact, address, lat, lng) in projects.items():
                pid[key] = db.new_id()
                con.execute("INSERT INTO projects(id, name, short, client, contact, address, lat, lng, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                            (pid[key], name, short, client, contact, address, lat, lng, db.now()))

            phid = {}

            def photo(key, scene, at, proj, by, gps=True, salt="", device=None, address=None):
                with open(os.path.join(HERE, "ornek_fotolar", f"{scene}.svg"), "rb") as f:
                    data = f.read() + salt.encode()
                i = db.new_id()
                name = f"{i}.svg"
                with open(os.path.join(photos_dir, name), "wb") as f:
                    f.write(data)
                lat, lng = (projects[proj][5], projects[proj][6]) if gps else (None, None)
                src, acc = ("project" if gps else "none"), None
                if device:  # sahada cihaz konumuyla çekilmiş gibi
                    lat, lng, acc, src = device[0], device[1], device[2], "device"
                con.execute("""INSERT INTO photos(id, sha256, path, thumb_path, mime, width, height, taken_at, lat, lng,
                               gps_source, gps_accuracy, address, uploaded_by, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                            (i, hashlib.sha256(data).hexdigest(), name, name, "image/svg+xml", 800, 600, at, lat, lng,
                             src, acc, address, uid[by], at))
                phid[key] = i

            def ann(photo_key, x, y, text, by):
                con.execute("INSERT INTO annotations(id, photo_id, x, y, text, by_id, created_at) VALUES (?,?,?,?,?,?,?)",
                            (db.new_id(), phid[photo_key], x, y, text, uid[by], db.now()))

            photo("ph1", "leak-before", _ts(-3, 9, 14), "p1", "u2")
            photo("ph2", "crack-before", _ts(-6, 10, 2), "p1", "u3")
            photo("ph3", "crack-progress", _ts(-4, 15, 40), "p1", "u3")
            photo("ph4", "crack-after", _ts(-1, 16, 25), "p1", "u3")
            photo("ph5", "panel-before", _ts(-1, 11, 5), "p2", "u1")
            photo("ph6", "ac-before", _ts(-5, 9, 40), "p2", "u3")
            photo("ph7", "ac-after", _ts(-3, 11, 10), "p2", "u3")
            photo("ph8", "tile-before", _ts(-2, 13, 30), "p3", "u1")
            photo("ph9", "gutter-before", _ts(0, 8, 50), "p3", "u2")
            photo("ph10", "leak-before", _ts(0, 14, 32), "p1", "u2", gps=False, salt="<!-- 2 -->")
            # Sahada cihaz konumuyla çekilmiş fotoğraflar: adresleri fotoğraftan bulunmuş
            photo("ph11", "tile-before", _ts(-1, 10, 12), "p1", "u2", salt="<!-- 3 -->",
                  device=(41.03045, 29.04395, 9.0), address="Kuzguncuk Mah., İcadiye Cd. No 41, Üsküdar/İstanbul")
            photo("ph12", "gutter-before", _ts(-1, 10, 20), "p1", "u2", salt="<!-- 4 -->",
                  device=(41.03052, 29.04402, 12.0), address="Kuzguncuk Mah., İcadiye Cd. No 41, Üsküdar/İstanbul")
            photo("ph13", "panel-after", _ts(-1, 15, 2), "p2", "u1", salt="<!-- 5 -->",
                  device=(40.99245, 29.12462, 6.0), address="Barbaros Mah., Halk Cd. No 10, Ataşehir/İstanbul")
            photo("ph14", "crack-after", _ts(-2, 9, 40), "p1", "u3", salt="<!-- 6 -->",
                  device=(40.98611, 29.02708, 8.0), address="Caferağa Mah., Moda Cd. No 112, Kadıköy/İstanbul")
            ann("ph1", 52, 41, "Lekenin merkezi, üst kat banyo gideri hizası", "u1")
            ann("ph1", 51, 22, "Bağlantı parçasında paslanma", "u2")
            ann("ph2", 40, 34, "Çatlak yaklaşık 2,4 m, en geniş yeri 3 mm", "u3")
            ann("ph5", 50, 20, "Sigortaların hiçbiri etiketli değil", "u1")
            ann("ph5", 46, 64, "Kablolar kanal dışında, düzenlenecek", "u1")
            ann("ph8", 50, 62, "Forklift geçişinde kırılmış", "u1")

            def task(no, title, proj, status, assignee, due, priority, photos, checklist=(), comments=(), activity=(), untitled=0):
                tid = db.new_id()
                created = activity[0][0] if activity else db.now()
                con.execute("""INSERT INTO tasks(id, no, project_id, title, untitled, status, assignee_id, due, priority,
                               created_by, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                            (tid, no, pid[proj], title, untitled, status, uid[assignee] if assignee else None, due, priority,
                             uid["u1"], created, created))
                for key, ptype in photos:
                    con.execute("INSERT INTO task_photos(task_id, photo_id, type, created_at) VALUES (?,?,?,?)",
                                (tid, phid[key], ptype, created))
                for i, (text, done, proof, required) in enumerate(checklist):
                    con.execute("INSERT INTO checklist(id, task_id, text, done, require_proof, proof_photo_id, sort) VALUES (?,?,?,?,?,?,?)",
                                (db.new_id(), tid, text, 1 if done else 0, 1 if required else 0, phid[proof] if proof else None, i))
                for by, text, at in comments:
                    con.execute("INSERT INTO comments(id, task_id, by_id, text, created_at) VALUES (?,?,?,?,?)",
                                (db.new_id(), tid, uid[by], text, at))
                for at, by, text in activity:
                    con.execute("INSERT INTO activity(task_id, by_id, text, created_at) VALUES (?,?,?,?)",
                                (tid, "sys" if by == "sys" else uid[by], text, at))
                return tid

            task(141, "Banyo tavanında su sızıntısı", "p1", "progress", "u2", _day(-1), "high", [("ph1", "before")],
                 checklist=[("Ana vana kapatıldı", True, "ph1", False), ("Arızalı bağlantı parçası değişti", False, None, True),
                            ("Tavan kurutuldu, nem ölçüldü", False, None, False)],
                 comments=[("u1", "Üst kat sakiniyle görüştüm, yarın 09:00 sonrası daireye girilebilir.", _ts(-2, 18, 4)),
                           ("u2", "Bağlantı parçası sipariş edildi, ½\" pirinç.", _ts(-1, 10, 20))],
                 activity=[(_ts(-3, 9, 14), "u2", "Fotoğraftan iş oluşturdu"), (_ts(-3, 9, 30), "u1", "Saha Bir kişisine atadı"),
                           (_ts(-2, 8, 55), "u2", "Durumu “Devam ediyor” yaptı")])
            task(142, "Salon duvarında çatlak onarımı", "p1", "review", "u3", _day(1), "normal",
                 [("ph2", "before"), ("ph3", "progress"), ("ph4", "after")],
                 checklist=[("Çatlak açıldı ve temizlendi", True, "ph3", True), ("File ve sıva uygulandı", True, "ph3", False),
                            ("Boya iki kat", True, "ph4", True)],
                 activity=[(_ts(-6, 10, 2), "u3", "Fotoğraftan iş oluşturdu"), (_ts(-4, 15, 40), "u3", "Süreç fotoğrafı ekledi"),
                           (_ts(-1, 16, 25), "u3", "Sonra fotoğrafı ekledi"), (_ts(-1, 16, 25), "sys", "Otomasyon: “Onay bekliyor”a taşındı")])
            task(143, "Elektrik panosu düzenleme ve etiketleme", "p2", "open", "u2", _day(3), "normal", [("ph5", "issue")],
                 checklist=[("Enerji kesildi, kilit-etiket uygulandı", False, None, True), ("Her sigorta etiketlendi", False, None, True)],
                 activity=[(_ts(-1, 11, 5), "u1", "Fotoğraftan iş oluşturdu")])
            task(144, "Klima filtre bakımı (3. kat)", "p2", "done", "u3", _day(-3), "normal", [("ph6", "before"), ("ph7", "after")],
                 checklist=[("Filtreler söküldü, yıkandı", True, "ph7", True), ("Drenaj hattı kontrol edildi", True, None, False)],
                 activity=[(_ts(-5, 9, 40), "u3", "Fotoğraftan iş oluşturdu"), (_ts(-3, 11, 10), "u3", "Sonra fotoğrafı ekledi"),
                           (_ts(-3, 14, 0), "u1", "Onayladı")])
            task(145, "Kırık zemin karosu – yükleme rampası", "p3", "open", None, _day(5), "high", [("ph8", "issue")],
                 activity=[(_ts(-2, 13, 30), "u1", "Fotoğraftan iş oluşturdu")])
            task(146, "Yağmur oluğu temizliği", "p3", "progress", "u2", _day(0), "normal", [("ph9", "before")],
                 activity=[(_ts(0, 8, 50), "u2", "Fotoğraftan iş oluşturdu")])
            task(147, "Başlıksız iş · 14:32", "p1", "open", "u2", _day(2), "normal", [("ph10", "issue")],
                 activity=[(_ts(0, 14, 32), "u2", "Fotoğraftan iş oluşturdu (başlık girilmedi)")], untitled=1)
            task(148, "Mutfak tezgâhı altı nem ve küf", "p4", "open", "u2", _day(1), "normal",
                 [("ph11", "issue"), ("ph12", "before")],
                 activity=[(_ts(-1, 10, 12), "u2", "Fotoğraftan iş oluşturdu"),
                           (_ts(-1, 10, 12), "u2", "Müşteri konumu bu fotoğraftan alındı (Kuzguncuk)")])
            task(149, "Pano kapağı contası", "p2", "progress", "u3", _day(4), "normal", [("ph13", "issue")],
                 activity=[(_ts(-1, 15, 2), "u1", "Fotoğraftan iş oluşturdu")])
            task(150, "Antre duvarı rötuş", "p1", "open", "u3", _day(6), "normal", [("ph14", "issue")],
                 activity=[(_ts(-2, 9, 40), "u3", "Fotoğraftan iş oluşturdu")])
            # Kuzguncuk: adres ve konum fotoğraftan; Ataşehir: fotoğraftan gelen farklı adres önerisi
            con.execute("UPDATE projects SET lat = 41.03045, lng = 29.04395, location_source = 'photo', "
                        "address = 'Kuzguncuk Mah., İcadiye Cd. No 41, Üsküdar/İstanbul', address_source = 'photo' WHERE id = ?", (pid["p4"],))
            con.execute("UPDATE projects SET suggested_address = 'Barbaros Mah., Halk Cd. No 10, Ataşehir/İstanbul' WHERE id = ?", (pid["p2"],))
            db.set_setting(con, "next_no", "151")
    finally:
        con.close()
