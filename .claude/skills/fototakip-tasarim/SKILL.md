---
name: fototakip-tasarim
description: FotoTakip arayüzünde ekran, bileşen, stil veya simge eklerken ya da değiştirirken kullan; mobil öncelikli kurallar, 5 stil ve simge seti burada.
---

# Arayüz ve tasarım

## İlke
Kullanıcı sahada, tek elle, çoğu zaman güneş altında. **Yazı değil görsel**: fotoğraf kartın kendisidir, durum renkli şeritle, sayılar simgeyle gösterilir. Açıklama paragrafı yazma; gerekiyorsa `title`/`aria-label` kullan.

## Yerleşim
- Telefon (<768px): üst çubuk + alt menü (5 öğe, ortada kamera).
- Tablet (≥768px): 88px ikonlu yan şerit.
- Masaüstü (≥1200px): 232px etiketli yan menü; iş ayrıntısı sağdan panel.
- Dokunma hedefi **en az 44px** (`.ib`, `.btn`, `.nav`). Güvenli alanlar `env(safe-area-inset-*)` ile.
- Alt menünün yüksekliği `--dock-h` değişkeninde; yan menüde 0'dır (`measureChrome`).

## Stiller (`html[data-style]`)
| id | Karakter |
|---|---|
| `sade` | Varsayılan, açık, petrol mavisi |
| `gece` | Koyu; harita karoları karartılır |
| `saha` | Güneş altı: saf siyah/beyaz, ikaz sarısı, 2px çizgi, büyük yazı |
| `okyanus` | Yuvarlak yazı, kenarsız yüzen kartlar, gradyan zemin |
| `orman` | Tırnaklı başlık, düz kâğıt kart, üst durum şeridi |
`auto` = sistem açık/koyu. Tercih `users.theme`'de ve `localStorage['ft-style']`'da saklanır.

Yeni renk eklerken belirteç kullan (`--accent`, `--surface`, `--s-progress` …); sabit renk yazma. Beş stilde de ekran görüntüsü al.

## Simgeler
`web/app.js` içinde `P` sözlüğü (24×24 çizgi yolları) ve `ic(ad, boyut)` yardımcısı. Boyutlar: `xs` 15, `s` 18, varsayılan 22, `l` 28. Yetenek simgeleri **`web/palettes.json`** dosyasından gelir (15 konu paleti, 114 simge); sunucu `SKILL_ICONS`'u aynı dosyadan üretir. `null` değerli simge `P` içindeki çekirdek simgedir. Yeni simge: palete ekle (bir simge yalnız bir palette), çizgi 24×24. Dış kaynak Tabler Icons (MIT, `web/vendor/tabler-icons-LICENSE`).

## Arka plan
- `#backdrop` sabit katman; `.bgfill.pal` (palet simgelerinden üretilen SVG desen + renk) / `.photo` / `.none`. Kartlar ve paneller opak kalır.
- Varsayılan: kişinin ilk yeteneğinin simgesi hangi paletteyse o desen, renk yeteneğin rengi (yeteneksiz: yönetim → `ofis`, teknisyen → `mekanik`).
- Kişi `users.bg` ile değiştirir (`''`, `none`, `pal:<id>`, `photo:<sürüm>`); sahip `bg_enabled`, `bg_choice`, `bg_upload` ile kilitler. Kişisel fotoğraf yalnızca sahibine görünür (başkasına 404).
- **Saha stilinde arka plan kapalıdır** (güneş altı okunurluk). Desen veri URL'si `style="…"` içine girdiği için tek tırnakla yazılır.

## Erişilebilirlik
Yalnız simgeli düğmede `aria-label` zorunlu. Odak halkası görünür kalır. `prefers-reduced-motion` desteklenir.
