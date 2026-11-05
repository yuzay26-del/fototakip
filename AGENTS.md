# AGENTS.md — FotoTakip

Bu dosya, bu repoda çalışan TÜM yapay zeka ajanları için bağlayıcı kurallardır.
Tasarım dokümanı ile çelişirse bu dosya geçerlidir; çelişkiyi Issue olarak bildir.

## Proje özeti
FotoTakip, fotoğraf tabanlı bir iş takibi uygulamasıdır. Her iş bir fotoğrafla açılır
("önce") ve bir fotoğrafla kapanır ("sonra"). Aynı kod iki modda çalışır:

| Mod | Veritabanı | Fotoğraf deposu | Kuyruk |
| --- | --- | --- | --- |
| termux | SQLite | Yerel klasör | asyncio (süreç içi) |
| server | PostgreSQL | MinIO / S3 | Redis + worker |

Mod yalnızca `.env` ile seçilir (`DATABASE_URL`, `STORAGE_BACKEND`, `QUEUE_BACKEND`).
Kodda `if termux` / `if server` dalı YASAKTIR. Fark sadece `backend/app/adapters/` altında yaşar.

## Klasör sahipliği
| Klasör | Sahibi | Diğer ajanlar |
| --- | --- | --- |
| `docs/`, `docs/adr/`, `api/openapi.yaml` | architect | salt okuma |
| `backend/app/models/`, `backend/alembic/` | architect | salt okuma |
| `backend/app/` (models hariç) | backend | salt okuma |
| `web/src/` | frontend | salt okuma |
| `web/src/api/` (üretilmiş istemci) | KİMSE elle düzenlemez | `npm run gen:api` ile üretilir |
| `backend/tests/`, `web/e2e/`, `scripts/` | tester | salt okuma |
| `.github/` | ana oturum (orkestratör) | salt okuma |

Sahibi olmadığın bir dosyayı değiştirmen gerekiyorsa: değiştirme, PR açıklamasına
"Bağımlılık:" başlığıyla yaz ya da Issue aç.

## Sözleşme önce
1. Yeni veya değişen her uç nokta önce `api/openapi.yaml` içinde tanımlanır (architect).
2. İnsan (Yusuf) sözleşme PR'ını onaylamadan backend ve frontend o uç noktaya kod yazmaz.
3. Frontend, API çağrılarını yalnızca üretilmiş istemci üzerinden yapar; elle `fetch` yazılmaz.

## Teknoloji kuralları
- Python 3.12, FastAPI, SQLAlchemy 2 (async), Alembic, Pydantic v2, Pillow.
- Frontend: React 18 + TypeScript (strict) + Vite, Tailwind, shadcn/ui, TanStack Query.
- Tüm kimlikler UUID. Tüm zamanlar UTC, ISO 8601.
- Fotoğraf koordinatları (işaretler) 0–1 arası oransal değerdir, piksel değil.
- `backend/requirements-termux.txt` içine yalnızca saf Python veya Termux'ta `pkg` ile hazır gelen
  paketler eklenebilir. OpenCV, torch, numpy-derleme isteyen paketler YASAK. Ağır paketler
  sadece `requirements.txt` (server) içine girer ve kod içinde isteğe bağlı import edilir.
- Sırlar (.env, anahtarlar) asla commit edilmez. Örnekler `deploy/.env.example` içindedir.

## Komutlar
```bash
# Backend
cd backend && pytest -q
cd backend && ruff check . && ruff format --check .
cd backend && alembic upgrade head

# Frontend
cd web && npm run gen:api
cd web && npm run lint && npm run typecheck && npm test
cd web && npx playwright test

# Termux kurulum testi (konteyner)
./scripts/test-termux-install.sh
```
Bir PR açmadan önce kendi alanının komutlarını çalıştır ve çıktının özetini PR açıklamasına ekle.

## Dal ve PR kuralları
- Dal adı: `agent/<rol>/<issue-no>-<kisa-ad>` (örn. `agent/backend/42-photo-upload`).
- Her ajan kendi git worktree'sinde çalışır. `main` dalına doğrudan commit YASAK.
- Bir PR en fazla ~400 satır değişiklik (üretilmiş dosyalar ve lock dosyaları hariç).
  Daha büyükse böl.
- Commit mesajı: Conventional Commits (`feat:`, `fix:`, `test:`, `docs:`, `refactor:`).
- PR açıklaması şablonu:
  ```
  Issue: #<no>
  Ne değişti:
  Nasıl test edildi: (komutlar + sonuç)
  Bağımlılık: (varsa başka ajanın işi)
  Risk / açık soru:
  ```
- CI kırmızıysa PR "hazır" işaretlenmez.

## Yapma listesi
- Testi geçirmek için testi silme veya zayıflatma.
- Görevde istenmeyen yeniden düzenleme (refactor) yapma.
- Yeni bağımlılık eklerken gerekçeyi PR'a yazmadan ekleme.
- Uydurma API, tablo veya alan kullanma; emin değilsen `api/openapi.yaml` ve modellere bak.
- Gerçek telefon testi gerektiren bir şeyi (kamera, çevrimdışı senkron, pil) "test edildi" diye işaretleme;
  bunu PR'da "Telefonda doğrulanmalı" olarak yaz.
