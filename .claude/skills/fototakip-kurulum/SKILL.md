---
name: fototakip-kurulum
description: FotoTakip'i Android telefonda Termux ile kurmak, güncellemek, ilk yönetici hesabını açmak, sıfırlamak ya da kurulum hatalarını çözmek gerektiğinde kullan.
---

# FotoTakip kurulumu (Termux)

## Kural
- Kullanıcının telefonuna verilecek komutlar `&&` ile zincirlenir. Dosya arayan adımlar önce dosyanın varlığını denetler (`[ -f "$P" ]`); boş değişkenle devam eden zincir yazma.
- `~/storage/downloads` yalnızca `termux-setup-storage` sonrası vardır.
- Komut çıktısı istemek için kullanıcıdan klasörün tamamını listelemesini isteme; `grep` ile daralt (İndirilenler'de kişisel dosyalar olur).

## İlk kurulum
```bash
curl -fsSL https://raw.githubusercontent.com/KULLANICI/fototakip/main/scripts/install.sh | bash -s -- --repo https://github.com/KULLANICI/fototakip.git
```
Seçenekler: `--dns opendns|cloudflare|google|quad9|dokunma`, `--tunel`, `--evet`, `--no-boot`.

Ardından `fototakip` komutu sunucuyu açar. Veritabanı boşsa Termux ekranına **kurulum kodu** yazar (ayrıca `~/fototakip-data/kurulum-kodu.txt`). Tarayıcıda `http://localhost:8080` → kod + ad + kullanıcı adı + parola (≥8). Bu hesap **sahip** rolündedir. 5 hatalı denemede kod geçersiz olur; yeniden başlatınca yenisi üretilir.

## Güncelleme
Aynı tek satır `--repo` olmadan çalışır; veri klasörüne dokunmaz. Veritabanı göçleri açılışta otomatik çalışır (`fototakip/db.py`, `MIGRATIONS`).

## Sıfırlama
`bash ~/fototakip/scripts/sifirla.sh` — sunucu ve tüneli durdurur, İndirilenler'e yedek alır (gizli anahtarlar hariç), `SIL` onayı ister, veri klasörünü siler, DNS'i geri alır, isteğe bağlı GitHub kimliğini siler. `--yedeksiz`, `--evet`, `--git-kimlik`.

## Sık hatalar
| Belirti | Neden | Çözüm |
|---|---|---|
| `fatal: could not open ''` | Yama/bundle dosyası inmemiş | Dosyayı sohbetten indir, `ls -t ~/storage/downloads \| grep -i fototakip` |
| Tünel "lookup" hatası | Termux DNS | `fototakip-dns opendns` |
| Konum alınamıyor | HTTP bağlantı | Telefonda `localhost`, diğer cihazlarda tünel (HTTPS) |
