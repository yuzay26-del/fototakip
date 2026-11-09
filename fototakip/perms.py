"""Yetki hiyerarşisi ve kullanıcı izolasyonu. Tüm kararlar burada; API uçları yalnızca bunları çağırır.

Roller (yüksekten düşüğe):
  owner    Sahip. Her şey; bağlantılar (tünel, AI anahtarı), yedek, yönetici ekleme.
  manager  Yönetici. Tüm işler ve müşteriler; ekip lideri ve teknisyen yönetimi.
  lead     Ekip lideri. Kendi ekibinin işleri + atanmamış işler; ekibine atama, onay; müşteri ekleme.
  field    Teknisyen. YALNIZCA kendisine atanmış işler ve o işlerin müşterileri.

İzolasyon sunucu tarafında uygulanır: görünmeyen kayıt 404 döner, liste uçları filtrelenir,
canlı olay akışı da kullanıcının göremeyeceği işleri iletmez.
"""

from __future__ import annotations

ROLES = ("owner", "manager", "lead", "field")
RANK = {"owner": 4, "manager": 3, "lead": 2, "field": 1}
ROLE_NAMES = {"owner": "Sahip", "manager": "Yönetici", "lead": "Ekip lideri", "field": "Teknisyen"}


def is_admin(user) -> bool:
    return user["role"] in ("owner", "manager")


def is_owner(user) -> bool:
    return user["role"] == "owner"


def team_ids(con, user) -> set[str]:
    """Ekip lideri için kendisi + ekibi; diğer roller için yalnızca kendisi."""
    ids = {user["id"]}
    if user["role"] == "lead":
        ids |= {r[0] for r in con.execute("SELECT id FROM users WHERE lead_id = ?", (user["id"],))}
    return ids


def task_filter(con, user) -> tuple[str, list]:
    """tasks tablosu (t takma adıyla) için WHERE parçası."""
    if is_admin(user):
        return "1=1", []
    if user["role"] == "lead":
        ids = sorted(team_ids(con, user))
        marks = ",".join("?" * len(ids))
        return f"(t.assignee_id IS NULL OR t.assignee_id IN ({marks}) OR t.created_by = ?)", [*ids, user["id"]]
    return "t.assignee_id = ?", [user["id"]]


def can_see_task(con, user, t) -> bool:
    if is_admin(user):
        return True
    if user["role"] == "lead":
        return t["assignee_id"] is None or t["created_by"] == user["id"] or t["assignee_id"] in team_ids(con, user)
    return t["assignee_id"] == user["id"]


def can_write_task(con, user, t) -> bool:
    if is_admin(user):
        return True
    if user["role"] == "lead":
        return can_see_task(con, user, t)
    return t["assignee_id"] == user["id"]


def can_review(con, user, t) -> bool:
    """Onaylama / tamamlandı yapma: yönetici veya işi gören ekip lideri."""
    return is_admin(user) or (user["role"] == "lead" and can_see_task(con, user, t))


def can_assign_to(con, user, target_id: str | None) -> bool:
    if target_id is None:
        return is_admin(user) or user["role"] == "lead"
    row = con.execute("SELECT id, active FROM users WHERE id = ?", (target_id,)).fetchone()
    if not row or not row["active"]:
        return False
    if is_admin(user):
        return True
    if user["role"] == "lead":
        return target_id in team_ids(con, user)
    return target_id == user["id"]


def visible_project_ids(con, user) -> set[str] | None:
    """None = hepsi. Teknisyen yalnızca kendi işlerinin müşterilerini görür."""
    if user["role"] in ("owner", "manager", "lead"):
        return None
    return {r[0] for r in con.execute("SELECT DISTINCT project_id FROM tasks WHERE assignee_id = ?", (user["id"],))}


def can_manage_customers(user) -> bool:
    return user["role"] in ("owner", "manager", "lead")


def creatable_roles(actor) -> tuple[str, ...]:
    if actor["role"] == "owner":
        return ROLES
    if actor["role"] == "manager":
        return ("lead", "field")
    return ()


def can_manage_user(actor, target) -> bool:
    """Kullanıcıyı düzenleme / pasifleştirme / parola sıfırlama."""
    if actor["id"] == target["id"]:
        return False  # kendi hesabını panelden değil, profilden değiştirir
    if actor["role"] == "owner":
        return True
    if actor["role"] == "manager":
        return target["role"] in ("lead", "field")
    return False


def visible_user_ids(con, user, task_ids: list[str]) -> set[str] | None:
    """None = hepsi. Diğerleri: kendisi, lideri, ekibi ve gördüğü işlerde adı geçenler."""
    if is_admin(user):
        return None
    ids = team_ids(con, user)
    if user.get("lead_id"):
        ids.add(user["lead_id"])
    if task_ids:
        marks = ",".join("?" * len(task_ids))
        for sql in (f"SELECT assignee_id FROM tasks WHERE id IN ({marks})",
                    f"SELECT created_by FROM tasks WHERE id IN ({marks})",
                    f"SELECT by_id FROM comments WHERE task_id IN ({marks})",
                    f"SELECT by_id FROM activity WHERE task_id IN ({marks})",
                    f"SELECT a.by_id FROM annotations a JOIN task_photos tp ON tp.photo_id = a.photo_id WHERE tp.task_id IN ({marks})",
                    f"SELECT p.uploaded_by FROM photos p JOIN task_photos tp ON tp.photo_id = p.id WHERE tp.task_id IN ({marks})"):
            ids |= {r[0] for r in con.execute(sql, task_ids) if r[0]}
    if user["role"] == "lead":  # atama yapabilmesi ve onaya gönderen yöneticiyi görebilmesi için yöneticiler
        ids |= {r[0] for r in con.execute("SELECT id FROM users WHERE role IN ('owner', 'manager')")}
    return ids


def event_for(con, user, ev: dict) -> dict:
    """Canlı olay akışı: görülemeyen işin kimliği ve yapanı iletilmez.

    Yine de içeriksiz bir "yenile" sinyali gider; böylece işi başkasına devredilen teknisyenin
    ekranından iş hemen kalkar. Sinyal hangi işin değiştiğini söylemez.
    """
    if ev.get("type") != "task" or is_admin(user):
        return ev
    t = con.execute("SELECT assignee_id, created_by FROM tasks WHERE id = ?", (ev.get("id"),)).fetchone()
    if t is not None and can_see_task(con, user, t):
        return ev
    return {"type": "refresh"}
