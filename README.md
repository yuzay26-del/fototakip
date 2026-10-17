# FotoTakip

Saha teknisyenleri için fotoğraf tabanlı iş takibi. Her iş bir fotoğrafla açılır ("önce") ve bir fotoğrafla kapanır ("sonra"); yönetici iki fotoğrafı karşılaştırıp onaylar.

[![CI](https://github.com/yuzay26-del/fototakip/actions/workflows/ci.yml/badge.svg)](https://github.com/yuzay26-del/fototakip/actions/workflows/ci.yml)

> **Durum:** Faz 1 geliştiriliyor. Aşağıdaki kurulum komutları, [#1 Repo iskeleti](https://github.com/yuzay26-del/fototakip/issues/1) birleşince çalışır hale gelir.
> Arayüzü şimdiden denemek için: [tıklanabilir demo](https://claude.ai/artifact/5Uhwpu4SXLC3C8SF5eoNRN).

## Ne yapar

- **Fotoğraftan iş:** Kamerayı aç, çek, proje ve türü seç. İş oluşur.
- **Kanban pano:** Kartın kapağı son fotoğraftır. Mobilde kaydırarak, masaüstünde sürükleyerek durum değiştirilir.
- **Fotoğraf üzerine işaret:** Sorunlu noktaya dokunup not bırakılır, not yorum olarak kaydedilir.
- **Önce / sonra karşılaştırma:** Kaydırıcıyla iki fotoğraf üst üste incelenir; yönetici onaylar ya da gerekçe yazarak geri gönderir.
- **Fotoğraflı kontrol listesi:** Her madde bir kanıt fotoğrafına bağlanabilir.
- **Galeri, takvim, harita:** Fotoğraflar türe göre, işler son tarihe ve konuma göre listelenir.
- **Müşteri raporu:** Proje için önce/sonra çiftlerinden teslim belgesi üretilir.
- **Çevrimdışı çekim:** İnternet yokken çekilen fotoğraflar kuyruğa alınır, bağlantı gelince yüklenir.

Hangi özelliğin hangi fazda geldiği [docs/ROADMAP.md](docs/ROADMAP.md) dosyasında.

## İki çalışma modu

Aynı kod iki modda çalışır; aradaki fark yalnızca `.env` dosyasındadır.

| Mod | Kimin için | Veritabanı | Fotoğraf deposu | Kuyruk |
| --- | --- | --- | --- | --- |
| `termux` | 1 kişi veya küçük ekip, tek Android telefon | SQLite | Telefon klasörü | Süreç içi |
| `server` | Onlarca kullanıcı | PostgreSQL | MinIO / S3 | Redis + worker |

Termux modunda OCR ve yapay zeka özellikleri kapalıdır; bu paketler telefonda derlenemez.

## Kurulum: Termux (Android)

1. Termux'u [F-Droid](https://f-droid.org/packages/com.termux/) veya [GitHub sürümünden](https://github.com/termux/termux-app/releases) kur. Play Store sürümü eski ve güncellenmiyor.
2. Termux'ta çalıştır:

```bash
curl -fsSL https://raw.githubusercontent.com/yuzay26-del/fototakip/main/scripts/install.sh | bash
```

Betik şunları yapar: sistem paketlerini kurar, galeriye erişim izni ister, hazır derlenmiş arayüzü indirir, veritabanını oluşturur ve sunucuyu `8080` portunda başlatır.

3. **HTTPS bağlantısı aç.** Bu adım isteğe bağlı değil.

Tarayıcılar kamera, konum, bildirim ve çevrimdışı çalışmayı yalnızca HTTPS'te açar. `http://192.168.x.x:8080` adresinden bağlanan diğer telefonlarda bu özelliklerin hiçbiri çalışmaz.

```bash
pkg install cloudflared
cloudflared tunnel --url http://localhost:8080
```

Çıktıdaki `https://….trycloudflare.com` adresini ekiptekilerle paylaş. Bu adres her başlatmada değişir; kalıcı adres için Cloudflare hesabına bağlı adlandırılmış bir tunnel kullan.

4. **Telefonun sunucuyu kapatmasını engelle:**
   - Android ayarlarında Termux için pil optimizasyonunu kapat.
   - Telefon açılınca otomatik başlaması için [Termux:Boot](https://f-droid.org/packages/com.termux.boot/) eklentisini kur. Kurulum betiği `~/.termux/boot/fototakip.sh` dosyasını oluşturur.

Fotoğraflar `~/storage/shared/FotoTakip/` altında durur. Günlük yedek almayı unutma: telefon kaybolursa bütün veri gider.

## Kurulum: Sunucu (Docker)

```bash
git clone https://github.com/yuzay26-del/fototakip.git
cd fototakip/deploy
cp .env.example .env        # SECRET_KEY ve parolaları değiştir
docker compose up -d
```

Uygulama `http://localhost:8080` adresinde açılır. Dışarıya açmadan önce önüne HTTPS sağlayan bir ters vekil koy (Caddy, Traefik veya Cloudflare Tunnel).

Termux'tan sunucuya geçiş: SQLite verisini ve fotoğraf klasörünü taşıyan bir betik Faz 3'te eklenecek.

## Yapılandırma

| Değişken | Termux örneği | Sunucu örneği | Açıklama |
| --- | --- | --- | --- |
| `DATABASE_URL` | `sqlite+aiosqlite:///./fototakip.db` | `postgresql+asyncpg://fototakip:…@db/fototakip` | Veritabanı |
| `STORAGE_BACKEND` | `local` | `s3` | Fotoğraf deposu |
| `MEDIA_ROOT` | `~/storage/shared/FotoTakip` | — | Yerel depo klasörü |
| `S3_ENDPOINT`, `S3_BUCKET`, `S3_KEY`, `S3_SECRET` | — | `http://minio:9000`, `fototakip`, … | S3 uyumlu depo |
| `QUEUE_BACKEND` | `inprocess` | `redis` | Arka plan işleri |
| `REDIS_URL` | — | `redis://redis:6379/0` | Kuyruk bağlantısı |
| `SECRET_KEY` | uzun rastgele değer | uzun rastgele değer | Oturum anahtarı imzası |
| `MAX_UPLOAD_MB` | `15` | `15` | Tek fotoğraf için yükleme sınırı |

Örnek dosyalar: `backend/.env.termux` ve `deploy/.env.example`. `.env` dosyasını asla commit etme.

## Mimari

```
PWA arayüz (React + Vite)
        │ HTTPS · REST + WebSocket
        ▼
FastAPI çekirdeği ──► Veritabanı   (SQLite | PostgreSQL)
        │         ──► Fotoğraf     (klasör | MinIO / S3)
        │         ──► Kuyruk       (asyncio | Redis)
        ▼
Görüntü işleyici: küçük resim, EXIF, GPS · OCR yalnızca sunucuda
```

Kararların gerekçeleri `docs/adr/` klasöründe.

## Repo yapısı

```
backend/    FastAPI uygulaması, modeller, göçler, testler
web/        React + TypeScript arayüz
api/        openapi.yaml: API sözleşmesi
scripts/    Termux kurulum ve test betikleri
deploy/     docker-compose.yml ve .env.example
docs/       yol haritası, ADR'ler, elle test adımları
```

## Geliştirme

Gerekenler: Python 3.12, Node 20+, Docker (PostgreSQL testleri için).

```bash
# Backend
cd backend
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8080
pytest -q
ruff check . && ruff format --check .

# Arayüz
cd web
npm install
npm run gen:api      # api/openapi.yaml'dan istemci üretir
npm run dev
npm run lint && npm run typecheck && npm test
```

API sözleşmesi önce gelir. Yeni bir uç nokta önce `api/openapi.yaml`'a yazılır ve onaylanır, kod ondan sonra yazılır. `web/src/api/` klasörü üretilmiş koddur, elle düzenlenmez.

## Katkı

Bu projede kodun büyük kısmını yapay zeka ajanları yazıyor, birleştirme kararını insan veriyor. İnsan ya da ajan, katkı yapan herkes şu kurallara uyar:

- Kurallar: [AGENTS.md](AGENTS.md). Klasör sahipliği, dal adları, PR şablonu ve yasaklar burada.
- Ajan rolleri: `.claude/agents/` (architect, backend, frontend, tester, reviewer).
- `main` dalına doğrudan commit yok. Her değişiklik bir Issue'ya bağlı PR ile gelir ve CI yeşil olmadan birleşmez.
- Kamera, çevrimdışı senkron ve pil davranışı konteynerde test edilemez. Bu tür değişiklikler gerçek telefonda [docs/MANUAL_TEST.md](docs/MANUAL_TEST.md) adımlarıyla doğrulanır.

## Gizlilik

Fotoğraflar konum (GPS) ve çekim zamanı içerir. Müşteriye giden raporlarda ve paylaşım bağlantılarında konum bilgisi silinir. Konum kaydı proje bazında kapatılabilir.

## Lisans

Karar bekliyor: MIT veya AGPL-3.0. Bkz. [#1](https://github.com/yuzay26-del/fototakip/issues/1).
# fototakip
is takibi
