---
name: fototakip-yayin
description: FotoTakip değişikliklerini kullanıcının telefonuna ve GitHub deposuna teslim ederken kullan (yama, bundle, yükleme betiği, doğrulama).
---

# Teslim ve yayın

## Durum
Asistanın depoya yazma yetkisi yoksa değişiklik **dosya** olarak teslim edilir; kullanıcı telefonda uygular ve `scripts/github-upload.sh` ile yükler.

- Küçük değişiklik: `git format-patch` → `.patch`. Telefonda `git am`.
- Geçmiş yeniden yazıldıysa ya da kurulum baştan yapılacaksa: `git bundle` (yalnızca `main`). Telefonda `git clone -b main dosya.bundle`.

## Teslimden önce
1. GitHub'daki son sürümün temiz kopyasına uygula (`git am` / `git clone bundle`).
2. Testler + `uret.py --check` + `node --check web/app.js`.
3. Kişisel bilgi taraması: `git grep -n -i -E "ad|kullanıcıadı|@gmail|telefon"` (vendor hariç). Commit yazarı kişisel e-posta içermemeli.
4. Commit mesajı Türkçe, ne değiştiğini söyler.

## Telefon komutu kalıbı
```bash
cd ~ && B=$(ls -t ~/storage/downloads/*ADI* 2>/dev/null | head -1); if [ -f "$B" ]; then …; else echo "HATA: dosya yok, önce indir"; fi
```
Asla `P=$(ls … | head -1) && git am "$P"` yazma: `head` başarılı döndüğü için boş değişkenle devam eder.

## GitHub token
Sohbete yapıştırılmaz. Gerekirse: ince ayarlı, yalnızca bu depo, Contents: Read and write, 1 gün, iş bitince iptal.
