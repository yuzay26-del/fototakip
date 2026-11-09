# FotoTakip

Saha teknisyenleri için fotoğraf tabanlı iş takibi. Her iş bir fotoğrafla açılır ("önce") ve bir fotoğrafla kapanır ("sonra"). Yönetici iki fotoğrafı karşılaştırır, onaylar ya da gerekçe yazarak geri gönderir.

**Durum: v0.5.** Tek bir Android telefonda Termux ile çalışır; ekip aynı telefona tarayıcıdan bağlanır. Sunucu yalnızca Python standart kütüphanesini kullanır, derleme gerektiren paket yoktur.

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
| Roller | Sahip › Yönetici › Ekip lideri › Teknisyen. Teknisyen yalnızca kendisine atanmış işleri ve o işlerin müşterilerini görür (ayrıntı aşağıda). |
| Yönetim paneli | Müşteriler (telefon, e-posta, adres, not, arşiv), ekip ağacı (rol, ekip lideri, yetenek, açık/pasif, oturum kapatma), yetenekler, sistem ayarları. |
| Yetenekler | Elektrik, tesisat, klima… İşe yetenek seçilir; atamada o yetenekteki kişiler iş yüküne göre önerilir. |
| Görünüm | 5 stil: Sade, Gece, Saha (güneş altı yüksek kontrast), Okyanus, Orman. Telefon, tablet ve masaüstünde ayrı yerleşim. |
| Yedek | Sahip tek tıkla veritabanı ve fotoğrafları zip olarak indirir. |

Kaydedilen fotoğraflar döndürülür, 2560 px'e küçültülür ve EXIF'siz yazılır. Dosyada konum kalmaz; konum yalnızca veritabanında tutulur.

## Tek satırda kurulum veya güncelleme (Termux)

`KULLANICI` yerine deponun GitHub sahibini yaz:

```bash
curl -fsSL https://raw.githubusercontent.com/KULLANICI/fototakip/main/scripts/install.sh | bash -s -- --repo https://github.com/KULLANICI/fototakip.git
```

Kod yoksa indirir, varsa günceller ve kurar. Güncellemede `--repo` gerekmez. Verilere (`~/fototakip-data`) dokunmaz. Bittikten sonra `fototakip` yazıp başlat.

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
     git clone https://github.com/KULLANICI/fototakip.git ~/fototakip
     ```
3. **Kur ve başlat:**
   ```bash
   bash ~/fototakip/scripts/install-termux.sh
   fototakip
   ```
4. **İlk kurulum:** telefonun tarayıcısında `http://localhost:8080` adresine git. Kurulum ekranı açılır: Termux'ta yazan **kurulum kodunu**, adını, kullanıcı adını ve en az 8 karakterlik parolanı gir. Bu ilk hesap **sahip** rolündedir; müşterileri ve ekibi **Yönetim** bölümünden eklersin.
5. **Pil ayarı:** Ayarlar › Uygulamalar › Termux › Pil › **Kısıtlamasız**. Yapmazsan ekran kapanınca sunucu durabilir. Telefon açılınca kendiliğinden başlaması için [Termux:Boot](https://f-droid.org/packages/com.termux.boot/) uygulamasını da kur.

Uygulama boş başlar: hazır hesap, örnek müşteri ya da örnek iş yoktur. Kurulum kodu tek kullanımlıktır, `~/fototakip-data/kurulum-kodu.txt` dosyasında da durur (Termux:Boot ile başladıysa buradan oku) ve hesap açılınca silinir. 5 hatalı denemede geçersiz olur; FotoTakip'i yeniden başlatınca yeni kod üretilir.

### Her şeyi silip baştan kurmak

```bash
bash ~/fototakip/scripts/sifirla.sh
```

Sunucuyu ve tüneli durdurur, verileri İndirilenler klasörüne yedekler (OpenAI anahtarı ve tünel token'ı yedeğe girmez), sonra veritabanını, fotoğrafları, imzaları, oturumları, parolaları ve gizli ayarları siler. Termux DNS ayarını kurulumdan önceki hâline döndürür. Telefonda kayıtlı GitHub kimlik bilgisini silmeyi ayrıca sorar. Onay için `SIL` yazman istenir; geri dönüşü yalnızca yedektir.

## Roller ve izolasyon

| Rol | Görür | Yapar |
|---|---|---|
| Sahip | Her şey | Her şey; bağlantılar (tünel, DNS, AI anahtarı), yedek, yönetici ekleme |
| Yönetici | Tüm işler, müşteriler, kişiler | Ekip lideri ve teknisyen ekler/düzenler/pasifleştirir; yetenekler; iş ve müşteri siler |
| Ekip lideri | Ekibinin işleri, atanmamış işler, müşteri rehberi | Ekibine iş atar, onaylar ya da geri gönderir, müşteri ekler |
| Teknisyen | **Yalnızca kendisine atanmış işler** ve o işlerin müşterileri | Fotoğraf, işaret, kontrol listesi, yorum, imza; işi onaya gönderir |

Kısıtlar sunucuda uygulanır: görülmeyen iş, fotoğraf, imza dosyası ve arama sonucu 404 döner; canlı güncelleme akışı da başkasının işini iletmez. Teknisyen diğer kişilerin kullanıcı adını, telefonunu, yeteneklerini görmez. Pasif hesap giriş yapamaz ve açık oturumları kapanır.

## Yapay zeka ajanları için skill'ler

`.claude/skills/` altında beş skill var: geliştirme, yetki, tasarım, kurulum, yayın. Claude Code bu depoda açıldığında bunları kendiliğinden tanır; diğer ajanlar için giriş noktası `AGENTS.md`.

## Dışarıdan güvenli erişim (ücretsiz tünel)

Aynı Wi-Fi'deki telefonlar `http://<telefonun-ip>:8080` adresinden bağlanabilir. Ama kamera konumu, çevrimdışı açılış ve ana ekrana ekleme yalnızca HTTPS'te çalışır; sahadaki ekip de aynı ağda değildir. Bunun için uygulama ücretsiz bir Cloudflare tüneli açar. Bağlantı telefondan dışarıya doğru kurulur: modemde port açmak gerekmez, mobil veride de çalışır.

Uygulamada **Yönetim › Sistem › Dışarıdan erişim** (yalnız sahip):

| Tür | Gerekenler | Adres |
| --- | --- | --- |
| Hızlı tünel | Hiçbir şey (hesap yok, ücretsiz) | `https://….trycloudflare.com`, her başlatmada değişir |
| Kendi alan adım | Ücretsiz Cloudflare hesabı + Cloudflare'de yönetilen bir alan adı | Sabit, ör. `https://is.alanadin.com` |

- Eski bir kurulumdan kalan, parolası hâlâ `demo1234` olan hesap varsa tünel açılmaz. Ekran bu hesapları listeler ve oradan yeni parola verilebilir.
- Hatalı girişler sınırlıdır: kullanıcı başına 10 dakikada 5 deneme.
- Tünel token'ı veritabanında değil, `~/fototakip-data/secrets.json` dosyasında (0600 izinli) durur; yedek zip'ine girmez, ekranda yalnızca son 4 karakteri görünür.
- "Açılışta başlat" seçilirse tünel FotoTakip ile birlikte açılır (Termux:Boot ile telefon açılışında da).

Tünel için `cloudflared` gerekir: kurulumda sorulur ya da `pkg install cloudflared`. Komut satırından elle hızlı tünel açmak için `fototakip-tunel` hâlâ çalışır.

### DNS ayarı

Termux'ta `cloudflared` gibi programlar bazen telefonun DNS'ini bulamaz ve tünel "lookup" hatasıyla durur. Çözüm, Termux içinde bir DNS sunucusu seçmek: kurulumda menü olarak sorulur, sonra uygulamadaki Yönetim › Sistem ekranından ya da komutla değiştirilir:

```bash
fototakip-dns opendns      # ya da cloudflare, google, quad9; eski hâline dönmek için: geri
```

Bu ayar yalnızca Termux içindeki programları etkiler; telefonun geri kalanına dokunmaz. OpenDNS bir DNS çözücüsüdür; uygulamayı dışarıya açan şey tüneldir.

Kurulumu sorusuz yapmak için:

```bash
curl -fsSL https://raw.githubusercontent.com/KULLANICI/fototakip/main/scripts/install.sh | bash -s -- --repo https://github.com/KULLANICI/fototakip.git --dns opendns --tunel
```

## AI fotoğraf incelemesi (isteğe bağlı)

Bir fotoğraf için OpenAI'den gözlem notu alır: görünen hasar, açıkta kalan parçalar, etiketleme, fotoğraf kalitesi. **Karar vermez.** Her sonuçta "insan incelemesi zorunlu" yazar ve onay yine yöneticidedir.

- Açmak için: Yönetim › Sistem › AI fotoğraf incelemesi (sahip). OpenAI API anahtarını gir, modeli seç (varsayılan `gpt-4.1-mini`).
- İş ayrıntısında fotoğrafın altında **AI gözlemi al** düğmesi çıkar. Sonuç saklanır; aynı fotoğraf için tekrar ücret ödenmez. Yönetici "Yeniden incele" diyebilir.
- Fotoğraf OpenAI'ye gönderilmeden önce EXIF ve konum bilgisi silinir. Kullanım OpenAI hesabından ücretlendirilir.
- Örnek çizim fotoğraflar incelenemez; gerçek bir fotoğraf gerekir.

## Konum nereden geliyor

Öncelik sırası: fotoğrafın EXIF konumu → çekim anındaki cihaz konumu → müşterinin kayıtlı adresi.

Android'de EXIF konumuna güvenme:
- Samsung Kamera'da konum etiketi varsayılan olarak kapalıdır: Kamera › Ayarlar › **Konum etiketleri**.
- Chrome, galeriden seçilen fotoğraflarda konum bilgisini çoğu zaman siler.
- WhatsApp gibi uygulamalardan gelen fotoğraflarda konum bilgisi yoktur.

Bu yüzden asıl kaynak, fotoğrafın yüklendiği andaki cihaz konumudur. Cihaz konumu yalnızca güvenli bağlantıda çalışır: aynı telefonda `http://localhost:8080` adresinde ya da başka telefonlarda tünelin verdiği HTTPS adresinde. Düz `http://192.168…` adresinde konum alınamaz.

**Harita karoları ve adres bulma internet ister.** Harita karoları OpenStreetMap'ten gelir. Bakılan bölgeler telefonda önbelleğe alınır, internet yokken son bakılan bölge görünür. Adres bulma OpenStreetMap Nominatim'i kullanır: saniyede en fazla 1 istek gönderilir ve sonuçlar önbelleğe alınır. Bu açıkken fotoğraf koordinatları OpenStreetMap Vakfı'nın sunucusuna gider. Kapatmak için:

```bash
fototakip --geocoder off
```

## Yedek

- Uygulamadan: Yönetim › Sistem › **Yedek indir** (sahip).
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
fototakip/   sunucu: api.py (uç noktalar), perms.py (rol ve izolasyon), server.py (HTTP, SSE), db.py (şema, göçler), geo.py (uzaklık, adres bulma), images.py (EXIF, küçük resim), tunnel.py, ai_review.py
web/         arayüz: index.html, app.js, styles.css, sw.js, vendor/leaflet (derleme adımı yok)
scripts/     install.sh, install-termux.sh, github-upload.sh, backup.sh, sifirla.sh
.claude/     skills/: ajanlar için kurulum, geliştirme, yetki, tasarım, yayın rehberleri
tests/       API uçtan uca testleri; ornek_veri.py ve ornek_fotolar/ yalnızca testlerde kullanılır
```

## Proje haritası

[`docs/proje-haritasi.html`](docs/proje-haritasi.html): projenin bileşenlerini ve aralarındaki bağlantıları 6 katmanlı 3B bir haritada gösterir. Bir bileşene dokununca neyi çağırdığı, hangi tabloya yazdığı görünür; fotoğraftan iş gibi akışlar adım adım oynatılabilir.

```bash
python3 tools/proje-haritasi/uret.py           # kod değişince haritayı yeniden üret
python3 tools/proje-haritasi/uret.py --check   # güncel mi? (CI da bunu kontrol eder)
termux-open docs/proje-haritasi.html           # telefonda aç
```

Uç noktalar, tablo erişimleri ve arayüz çağrıları koddan otomatik çıkarılır. Çağrıların hangi ekrana ait olduğu, açıklamalar ve akışlar `uret.py` içinde elle tutulur. Yeni bir çağrı eşlenmemişse betik uyarı verir. Harita 3B kütüphanesini (three.js) internetten yükler.

## Bilinen sınırlar

- Tek telefon, tek SQLite dosyası. Onlarca eşzamanlı kullanıcı için tasarlanmadı.
- HEIC/HEIF fotoğraflar kabul edilmez. Samsung'da Kamera › Ayarlar › Gelişmiş › Yüksek verimli resimler kapalı olmalı.
- Canlı güncellemede her değişiklik tüm listeyi yeniden yükler. Yüzlerce işe kadar sorun çıkarmaz.
- Malzeme/parça ve sahada geçen süre takibi henüz yok.
- Harita şimdilik sokak haritası; uydu görüntüsü yok (ücretsiz ve kullanım şartları uygun bir kaynak gerekiyor).
- Yapay zeka ajanlarıyla Faz 1 geliştirmesi (FastAPI + React iskeleti) bu dalda değil, `faz1-iskelet` dalında.

## Lisans

MIT, bkz. [LICENSE](LICENSE). Harita kütüphanesi Leaflet BSD-2 lisanslıdır (`web/vendor/leaflet/LICENSE`).
