---
name: fototakip-yetki
description: FotoTakip'te rol, izin, kullanıcı izolasyonu ya da yeni bir API ucunun kimin neyi görebileceğine karar verirken kullan.
---

# Yetki hiyerarşisi ve izolasyon

| Rol | Görür | Yapabilir |
|---|---|---|
| `owner` Sahip | Her şey | Her şey; bağlantılar (tünel, AI anahtarı, DNS), yedek, sahip/yönetici ekleme |
| `manager` Yönetici | Tüm işler, müşteriler, kişiler | Ekip lideri ve teknisyen yönetimi, yetenekler, müşteri silme, iş silme |
| `lead` Ekip lideri | Ekibinin işleri + atanmamış (havuz) işler + açtığı işler; müşteri rehberi | Ekibine atama, onay/geri gönderme, müşteri ekleme/düzenleme |
| `field` Teknisyen | **Yalnızca kendisine atanmış işler** ve o işlerin müşterileri | Kendi işinde fotoğraf, işaret, kontrol listesi, yorum, imza; onaya gönderme |

Ekip = `users.lead_id` (yalnızca teknisyenlerde dolu). Liderin rolü değişirse ekip dağılır.

## Uygulama kuralları
- Kararların tümü `fototakip/perms.py` içindedir: `task_filter`, `can_see_task`, `can_write_task`, `can_review`, `can_assign_to`, `visible_project_ids`, `visible_user_ids`, `can_manage_user`, `creatable_roles`, `event_for`.
- Görünmeyen kayıt **404**, görünen ama yetkisiz işlem **403**.
- Liste uçları sunucuda süzülür; istemci tarafı gizleme güvenlik sayılmaz.
- Canlı olay akışında görünmeyen iş için yalnızca içeriksiz `{"type": "refresh"}` gider.
- Kimse kendi hesabını yönetim panelinden düzenleyemez; son sahip pasifleştirilemez/düşürülemez.
- Pasif hesap giriş yapamaz, oturumları silinir, ona iş atanamaz.
- Teknisyen başkalarının kullanıcı adını, telefonunu, yeteneklerini görmez.

## Yeni uç eklerken kontrol listesi
1. Kim çağırabilir? (`need_manager`, `need_owner`, `need_customers` ya da `perms` fonksiyonu)
2. Hangi kayıtlara dokunuyor? Görünürlük denetimi `get_task` / `photo_visible` ile mi?
3. `tests/test_yetki.py`'ye teknisyen, lider ve ikinci yönetici için olumsuz test ekle.
