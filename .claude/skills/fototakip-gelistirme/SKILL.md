---
name: fototakip-gelistirme
description: FotoTakip koduna özellik eklerken, hata düzeltirken veya yeniden düzenlerken kullan; mimari, kod kuralları, testler, veritabanı göçleri ve proje haritası adımlarını içerir.
---

# FotoTakip geliştirme

## Mimari (kısaca)
- `fototakip/server.py` — `http.server` tabanlı sunucu, statik dosyalar, SSE (`/api/events`).
- `fototakip/api.py` — tüm uçlar `@route(...)` ile; `(req)` alır, dict döner ya da `ApiError` fırlatır.
- `fototakip/perms.py` — **tüm yetki kararları**. Bkz. `fototakip-yetki` skill'i.
- `fototakip/db.py` — SQLite (WAL), `SCHEMA` + `MIGRATIONS`, `db.tx(con)` ile yazma.
- `web/app.js` — derleme adımı olmayan tek dosya istemci; `S` durum nesnesi, `render()`; eylemler `data-act` / `data-change` / `data-form` ile `acts` / `changes` / `forms` sözlüklerine bağlanır.
- `web/styles.css` — tasarım belirteçleri ve 5 stil. Bkz. `fototakip-tasarim`.

## Kurallar
1. **Yalnızca Python standart kütüphanesi** (Pillow isteğe bağlı). Termux'ta derleme gerektiren paket ekleme.
2. İstemcide npm/derleme yok; harici CDN yok (çevrimdışı çalışmalı). Kütüphane gerekiyorsa `web/vendor/` altına konur.
3. Kullanıcıya görünen metin Türkçe, kısa, eylem adıyla aynı ("Kaydet" → "Kaydedildi").
4. Şema değişikliği = yeni `MIGRATIONS[n]` + `SCHEMA_VERSION`. Tablo yeniden kuruluyorsa `REBUILD_MIGRATIONS`'a ekle (yabancı anahtarlar göç sırasında kapanır, sonra `foreign_key_check`).
5. Yeni uç eklerken yetki denetimini `perms` ile yap, görünmeyen kayda **404** dön (varlığını sızdırma).

## Doğrulama (her değişiklikte)
```bash
python3 -m unittest discover -s tests            # Pillow'lu
PYTHONPATH=/yok/PIL-engeli python3 -m unittest discover -s tests   # Pillow'suz da geçmeli
python3 tools/proje-haritasi/uret.py && python3 tools/proje-haritasi/uret.py --check
node --check web/app.js
```
Arayüz değiştiyse Playwright ile telefon (390×844), tablet (834×1112) ve masaüstü (1440×900) ekran görüntüsü al ve bak.

## Test verisi
`tests/ornek_veri.py` (`seed_demo`) yalnızca testlerdedir: sahip `yonetici`, yönetici `yonetici2`, ekip lideri `lider`, teknisyenler `saha1` (liderin ekibinde), `saha2`. Uygulama bu veriyi asla yüklemez.
