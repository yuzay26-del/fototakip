# FotoTakip

Saha teknisyenleri için fotoğraf tabanlı iş takibi. Her iş bir fotoğrafla açılır ("önce") ve bir fotoğrafla kapanır ("sonra"). Yönetici iki fotoğrafı karşılaştırır, onaylar ya da gerekçe yazarak geri gönderir.

[![CI](https://github.com/yuzay26-del/fototakip/actions/workflows/ci.yml/badge.svg)](https://github.com/yuzay26-del/fototakip/actions/workflows/ci.yml)

**Durum: çalışan demo (v0.2).** Tek bir Android telefonda Termux ile çalışır; ekip aynı telefona tarayıcıdan bağlanır. Sunucu yalnızca Python standart kütüphanesini kullanır, derleme gerektiren paket yoktur.

## Ne yapar

| Özellik | Ayrıntı |
| --- | --- |
| Fotoğraftan iş | Kamerayla çek ya da galeriden seç, proje ve tür seç: iş oluşur. Birden fazla fotoğraf tek işe gider. |
| Pano | Kanban, liste ve takvim görünümü. Mobilde kart kaydırılarak, masaüstünde sürüklenerek durum değişir. |
| Havuz | Atanmamış işleri saha ekibi görür ve "Üstlen" ile kendine alır. |
| Fotoğraf üzerine işaret | Sorunlu noktaya dokunup not bırakılır; not yorum olarak da kaydedilir. |
| Önce / sonra | Kaydırıcıyla iki fotoğraf üst üste karşılaştırılır. |
| Kontrol listesi | Maddeler fotoğraf kanıtına bağlanır. "Foto zorunlu" maddeler kanıtsız işaretlenemez. |
| Otomasyon | "Sonra" fotoğrafı gelince iş "Onay bekliyor"a geçer. Bunun için önce fotoğrafı olmalı ve zorunlu kanıtlar tamamlanmış olmalı. |
| Onay | Yönetici onaylar veya gerekçe yazarak geri gönderir; kartta "Geri gönderildi" görünür. |
| Müşteri imzası | Parmakla imza ve imzalayanın adı; raporda görünür. |
| Harita | OpenStreetMap üzerinde müşteri pinleri: içinde açık iş sayısı, geciken iş varsa kırmızı, altında müşteri adı. Pine dokununca adres, yetkili, uzaklık, açık işler ve Google Haritalar yol tarifi açılır. |
| Mevcut konum | Hedef düğmesi mavi nokta ve doğruluk dairesiyle konumunu gösterir; liste "Yakınımdaki müşteriler" olarak uzaklığa göre sıralanır. |
| Fotoğraftan adres | Fotoğrafın konumu adrese çevrilir (OpenStreetMap Nominatim). Müşterinin adresi boşsa otomatik yazılır. Doluysa ve farklıysa "Bu adresi kullan" önerisi çıkar. Müşterinin konumu yoksa ilk konumlu fotoğraf konumu olur. |
| Yakın müşteri | Kamera açılınca 300 m içindeki müşteri otomatik seçilir. Yakında kayıtlı müşteri yoksa "Bu konumda yeni müşteri ekle" önerilir. |
| Konum uyarısı | Fotoğraf seçilen müşteriden 500 m'den uzakta çekildiyse uyarı verir ve etkinlik geçmişine yazar. |
| Haritadan müşteri | Yönetici haritaya dokunarak ya da bulunduğu yeri kullanarak müşteri ekler; adres otomatik gelir. Yanlış konum "Konumu düzelt" ile değiştirilir. |
| Konum kaynağı | Her fotoğrafta konumun nereden geldiği yazar: EXIF, cihaz (±doğruluk) ya da proje adresi. |
| Galeri, rapor | Galeri fotoğraf türüne göre süzülür. Rapor önce/sonra çiftlerinden oluşur, tarayıcıdan yazdırılır ya da PDF'e kaydedilir. |
| Çevrimdışı | Bağlantı yokken çekilen fotoğraflar telefonda kuyruğa alınır, bağlantı gelince sırayla yüklenir. |
| Canlı güncelleme | Biri işi değiştirince diğer ekranlar birkaç saniye içinde yenilenir. |
| Roller | Yönetici her şeyi görür. Saha teknisyeni yalnızca kendi işlerini ve havuzu görür, işi tamamlayamaz. |
| Yedek | Yönetici tek tıkla veritabanı ve fotoğrafları zip olarak indirir. |

Kaydedilen fotoğraflar döndürülür, 2560 px'e küçültülür ve EXIF'siz yazılır. Dosyada konum kalmaz; konum yalnızca veritabanında tutulur.

## Tek satırda kurulum veya güncelleme (Termux)

```bash
curl -fsSL https://raw.githubusercontent.com/yuzay26-del/fototakip/main/scripts/install.sh | bash
```

Kod yoksa indirir, varsa günceller ve kurar. Verilere (`~/fototakip-data`) dokunmaz. Bittikten sonra `fototakip` yazıp başlat.

## Telefona kurulum: adım adım (Termux)

1. **Termux'u kur:** [F-Droid](https://f-droid.org/packages/com.termux/) veya [GitHub sürümü](https://github.com/termux/termux-app/releases). Play Store sürümü eski ve güncellenmiyor.
2. **Kodu telefona al.** İki yol var:
   - Zip dosyasıyla:
     ```bash
     termux-setup-storage                     # İndirilenler klasörüne erişim izni
     pkg install -y unzip
     unzip ~/storage/downloads/fototakip.zip -d ~
     ```
   - GitHub'dan:
     ```bash
     pkg install -y git
     git clone https://github.com/yuzay26-del/fototakip.git ~/fototakip
     ```
3. **Kur ve başlat:**
   ```bash
   bash ~/fototakip/scripts/install-termux.sh
   fototakip
   ```
4. **Aç:** telefonun tarayıcısında `http://localhost:8080` adresine git. Örnek hesaplar `yusuf` (yönetici), `mert` ve `elif`; hepsinin parolası `demo1234`.
5. **Pil ayarı:** Ayarlar › Uygulamalar › Termux › Pil › **Kısıtlamasız**. Yapmazsan ekran kapanınca sunucu durabilir. Telefon açılınca kendiliğinden başlaması için [Termux:Boot](https://f-droid.org/packages/com.termux.boot/) uygulamasını da kur.

Örnek veri istemiyorsan ilk açılışta `fototakip --no-demo` çalıştır. Bu durumda tek bir yönetici hesabı açılır ve parolası ekrana yazılır.

## Diğer telefonlardan bağlanma ve HTTPS

Aynı Wi‑Fi'deki telefonlar `http://<telefonun-ip>:8080` adresinden bağlanabilir; adres, `fototakip` başlatılınca ekrana yazılır. Ama tarayıcılar cihaz konumunu, çevrimdışı açılışı ve ana ekrana eklemeyi yalnızca HTTPS'te açar. Fotoğraf çekme ve yükleme HTTP'de de çalışır.

HTTPS adresi açmak için ikinci bir Termux oturumunda:

```bash
fototakip-tunel
```

Çıkan `https://….trycloudflare.com` adresini ekiple paylaş. Bu adres her başlatmada değişir ve bağlantıyı bilen herkes giriş ekranına ulaşabilir. Örnek hesapların parolalarını değiştir ya da `--no-demo` ile başla.

## Konum nereden geliyor

Öncelik sırası: fotoğrafın EXIF konumu → çekim anındaki cihaz konumu → müşterinin kayıtlı adresi.

Android'de EXIF konumuna güvenme:
- Samsung Kamera'da konum etiketi varsayılan olarak kapalıdır: Kamera › Ayarlar › **Konum etiketleri**.
- Chrome, galeriden seçilen fotoğraflarda konum bilgisini çoğu zaman siler.
- WhatsApp gibi uygulamalardan gelen fotoğraflarda konum bilgisi yoktur.

Bu yüzden asıl kaynak, fotoğrafın yüklendiği andaki cihaz konumudur. Cihaz konumu yalnızca güvenli bağlantıda çalışır: aynı telefonda `http://localhost:8080` adresinde ya da başka telefonlarda `fototakip-tunel` ile açılan HTTPS adresinde. Düz `http://192.168…` adresinde konum alınamaz.

**Harita karoları ve adres bulma internet ister.** Harita karoları OpenStreetMap'ten gelir. Bakılan bölgeler telefonda önbelleğe alınır, internet yokken son bakılan bölge görünür. Adres bulma OpenStreetMap Nominatim'i kullanır: saniyede en fazla 1 istek gönderilir ve sonuçlar önbelleğe alınır. Bu açıkken fotoğraf koordinatları OpenStreetMap Vakfı'nın sunucusuna gider. Kapatmak için:

```bash
fototakip --geocoder off
```

## Yedek

- Uygulamadan: Profil › **Yedek indir** (yönetici).
- Termux'tan: `bash ~/fototakip/scripts/backup.sh`. Yedek, İndirilenler klasörüne gider.

Veriler `~/fototakip-data` klasöründe durur. Telefon kaybolursa yedeği olmayan veri gider.

## GitHub'a yükleme

```bash
bash scripts/github-upload.sh --check     # yalnızca durumu raporlar
bash scripts/github-upload.sh             # gerekiyorsa yükler ve doğrular
```

Betik şunları kontrol eder:

1. Depo GitHub'da var mı, erişim var mı?
2. Bu sürüm zaten yüklü mü? Yüklüyse hiçbir şey yapmaz.
3. GitHub'da burada olmayan commit var mı? Varsa üzerine yazmaz, durur.
4. Yüklemeden sonra GitHub'daki sürüm yereldekiyle aynı mı?

## Geliştirme

```bash
python3 -m fototakip --port 8080 --data ./data     # sunucu
python3 -m unittest discover -s tests -v           # testler (Pillow'lu ve Pillow'suz çalışır)
```

```
fototakip/   sunucu: api.py (uç noktalar), server.py (HTTP, SSE), db.py (şema, göçler), geo.py (uzaklık, adres bulma), images.py (EXIF, küçük resim), seed.py
web/         arayüz: index.html, app.js, styles.css, sw.js, vendor/leaflet (derleme adımı yok)
scripts/     install-termux.sh, github-upload.sh, backup.sh
tests/       API uçtan uca testleri
```

## Bilinen sınırlar

- Tek telefon, tek SQLite dosyası. Onlarca eşzamanlı kullanıcı için tasarlanmadı.
- HEIC/HEIF fotoğraflar kabul edilmez. Samsung'da Kamera › Ayarlar › Gelişmiş › Yüksek verimli resimler kapalı olmalı.
- Canlı güncellemede her değişiklik tüm listeyi yeniden yükler. Yüzlerce işe kadar sorun çıkarmaz.
- Malzeme/parça ve sahada geçen süre takibi henüz yok.
- Harita şimdilik sokak haritası; uydu görüntüsü yok (ücretsiz ve kullanım şartları uygun bir kaynak gerekiyor).
- Lisans henüz seçilmedi. Leaflet BSD-2 lisanslıdır (`web/vendor/leaflet/LICENSE`).
