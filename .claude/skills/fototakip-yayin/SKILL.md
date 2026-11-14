---
name: fototakip-yayin
description: FotoTakip değişikliklerini kullanıcının telefonuna ve GitHub deposuna teslim ederken kullan (yama, bundle, yükleme betiği, doğrulama).
---

# Teslim ve yayın

## Durum
**Önce doğrudan yüklemeyi dene.** Asistanın depoya yazma yetkisi varsa değişiklik `main` dalına doğrudan gönderilir; kullanıcı telefonda yalnızca tek satırlık kurulum komutunu yeniden çalıştırır (kod yoksa indirir, varsa günceller). Telefonun GitHub'a yükleme yapması, token üretmesi gerekmez.

Yetkiyi tahmin etme, ölç: depoya erişim iste, `git ls-remote` ile uzak durumu oku, gönder, sonra `git ls-remote` ile GitHub'daki commit'in yereldekiyle aynı olduğunu doğrula. "Yüklendi" demeden önce bu doğrulama şart; boş depoya işaret eden kurulum komutu verme.

Yalnızca yazma yetkisi gerçekten yoksa değişiklik **dosya** olarak teslim edilir; kullanıcı telefonda uygular ve `scripts/github-upload.sh` ile yükler.

- Küçük değişiklik: `git format-patch` → `.patch`. Telefonda `git am`.
- Geçmiş yeniden yazıldıysa ya da kurulum baştan yapılacaksa: `git bundle` (yalnızca `main`). Telefonda `git clone -b main dosya.bundle`.

## Teslimden önce
0. Depoda yalnızca bu projenin dosyaları olsun: `git ls-files` listesini gözden geçir (yabancı proje iskeleti, çift dosya, yedek zip, veri klasörü girmemeli).
1. GitHub'daki son sürümün temiz kopyasına uygula (`git am` / `git clone bundle`).
2. Testler + `uret.py --check` + `node --check web/app.js`.
3. Kişisel bilgi taraması: `git grep -n -i -E "ad|kullanıcıadı|@gmail|telefon"` (vendor hariç). Commit yazarı kişisel e-posta içermemeli.
4. Commit mesajı Türkçe, ne değiştiğini söyler.
5. Sürüm değiştiyse üç yer birlikte güncellenir: `fototakip/__init__.py`, `web/sw.js` içindeki `VERSION` (yoksa telefonlar eski arayüzü önbellekten açar) ve README'deki durum satırı.
6. Kurulum betiği değiştiyse temiz bir ev klasöründe uçtan uca dene: indirme, kurulum, `fototakip --version`, ikinci çalıştırmada "Zaten güncel".

## Telefon komutu kalıbı
```bash
cd ~ && B=$(ls -t ~/storage/downloads/*ADI* 2>/dev/null | head -1); if [ -f "$B" ]; then …; else echo "HATA: dosya yok, önce indir"; fi
```
Asla `P=$(ls … | head -1) && git am "$P"` yazma: `head` başarılı döndüğü için boş değişkenle devam eder.

## GitHub token
Sohbete yapıştırılmaz. Gerekirse: ince ayarlı, yalnızca bu depo, Contents: Read and write, 1 gün, iş bitince iptal.
