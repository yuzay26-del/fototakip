@AGENTS.md

# Ana oturum: Orkestratör

Bu oturum orkestratördür. Alt ajanlar başka alt ajan başlatamaz; işi dağıtan sensin.

## Görev akışı
1. Bir GitHub Issue al. Belirsizse kod yazmadan önce Yusuf'a en fazla 3 soru sor.
2. Issue'yu alt görevlere böl. Her alt görev tek bir role ve tek bir klasör alanına düşmeli.
3. Sıralama:
   - API veya veri modeli değişiyorsa önce `architect`. Sözleşme PR'ı insan onayı alana kadar bekle.
   - Sonra `backend` ve `frontend` paralel (ayrı worktree'lerde).
   - Ardından `tester`.
   - Her PR için en son `reviewer`.
4. Her alt ajana şunları ver: Issue numarası, dal adı, dokunabileceği dosyalar,
   kabul kriterleri, çalıştırması gereken komutlar.
5. Alt ajan bittiğinde çıktısını kendin kontrol et: CI komutları geçti mi, kapsam dışına taşmış mı?
6. Sonucu Issue'ya kısa bir yorumla raporla: hangi PR'lar açıldı, ne telefonda doğrulanmalı.

## Faz sınırı
Şu an hangi fazda olduğumuz `docs/ROADMAP.md` içindedir. Mevcut fazın dışındaki bir özelliğe
kod yazma; Issue'yu "sonraki-faz" etiketiyle işaretle.

## Durma noktaları (insan onayı şart)
- `api/openapi.yaml` veya veritabanı şeması değişikliği
- Yeni üçüncü taraf bağımlılık
- `requirements-termux.txt` değişikliği
- Güvenlik ile ilgili her şey (kimlik doğrulama, yetki, dosya erişimi)
- Veri silen göç (migration)
