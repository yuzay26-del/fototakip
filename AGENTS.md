# FotoTakip: yapay zeka ajanları için rehber

Bu depoda çalışan ajanlar (Claude Code ve benzerleri) önce ilgili skill'i okur. Skill'ler `.claude/skills/` altındadır:

| Skill | Ne zaman |
|---|---|
| `fototakip-gelistirme` | Kod değişikliği, test, göç, proje haritası |
| `fototakip-yetki` | Rol, izin, izolasyon, yeni API ucu |
| `fototakip-tasarim` | Ekran, bileşen, stil, simge |
| `fototakip-kurulum` | Termux kurulumu, güncelleme, sıfırlama, kurulum hataları |
| `fototakip-yayin` | Değişikliği telefona ve GitHub'a teslim etme |

`android/`: sunucuyu APK içinde çalıştıran Android projesi (Chaquopy + WebView). Python kodu oradan kopyalanmaz; `fototakip/` ve `web/` derlemede alınır. Giriş noktası `android/app/src/main/python/fototakip_android.py`, testi `tests/test_android.py`.

Değişmez kurallar: yalnızca Python standart kütüphanesi; istemcide derleme ve CDN yok; görünmeyen kayıt 404; her değişiklikte testler ve `tools/proje-haritasi/uret.py --check`; `android/` değiştiyse `cd android && ./gradlew assembleRelease`. İmza anahtarı (`android/keystore.properties`, `*.jks`) asla depoya girmez.
