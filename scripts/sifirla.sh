#!/usr/bin/env bash
# FotoTakip'i telefonda sıfırlar: tüm veriyi ve gizli ayarları siler, kod klasörüne dokunmaz.
# Kullanım:  bash scripts/sifirla.sh [--evet] [--yedeksiz] [--git-kimlik]
#   --evet        "SIL" onayını sorma (dikkat: geri dönüşü yalnızca yedek)
#   --yedeksiz    Silmeden önce yedek alma
#   --git-kimlik  Telefonda kayıtlı GitHub kimlik bilgisini de sormadan sil
#
# Sırayla: sunucuyu ve tüneli durdurur → verileri İndirilenler'e yedekler (gizli anahtarlar hariç)
# → veri klasörünü siler (veritabanı, fotoğraflar, imzalar, oturumlar, parolalar, secrets.json,
# kayıtlar) → Termux DNS ayarını kurulum öncesine döndürür → isteğe bağlı GitHub kimliğini siler.
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="${FOTOTAKIP_DATA:-$HOME/fototakip-data}"
ASSUME_YES=0
NO_BACKUP=0
GIT_CRED=""
while [ $# -gt 0 ]; do
  case "$1" in
    --evet|-y) ASSUME_YES=1; shift ;;
    --yedeksiz) NO_BACKUP=1; shift ;;
    --git-kimlik) GIT_CRED=1; shift ;;
    -h|--help) sed -n '2,10p' "$0"; exit 0 ;;
    *) echo "Bilinmeyen seçenek: $1" >&2; exit 2 ;;
  esac
done

say()  { printf '\033[1;36m▸ %s\033[0m\n' "$*"; }
ok()   { printf '\033[1;32m✓ %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m! %s\033[0m\n' "$*"; }
die()  { printf '\033[1;31m✗ %s\033[0m\n' "$*" >&2; exit 1; }
ask() {  # ask "soru" varsayılan -> ANSWER
  ANSWER="$2"
  if [ "$ASSUME_YES" = 0 ] && ( : > /dev/tty ) 2>/dev/null; then
    printf '%s ' "$1" > /dev/tty
    IFS= read -r ANSWER < /dev/tty || ANSWER="$2"
    [ -n "$ANSWER" ] || ANSWER="$2"
  fi
}

# Yanlış klasörü silmemek için: veri klasörü ev klasörünün kendisi, kök ya da kod klasörü olamaz.
case "$(cd "$DATA_DIR" 2>/dev/null && pwd || echo "$DATA_DIR")" in
  /|"$HOME"|"$APP_DIR"|"") die "Veri klasörü güvenli görünmüyor: $DATA_DIR" ;;
esac

echo "Silinecek: $DATA_DIR"
if [ -d "$DATA_DIR" ]; then
  du -sh "$DATA_DIR" 2>/dev/null | sed 's/^/  boyut: /' || true
else
  echo "  (klasör yok)"
fi

# ---------- 1. durdur ----------
say "Sunucu ve tünel durduruluyor"
stop_matching() {  # bu betiği ve onu çalıştıran kabuğu hariç tutarak durdurur
  local found=1 pid
  for pid in $(pgrep -f "$1" 2>/dev/null || true); do
    [ "$pid" = "$$" ] || [ "$pid" = "$PPID" ] && continue
    kill "$pid" 2>/dev/null && found=0
  done
  return $found
}
stop_matching "python[0-9.]* -m fototakip" && ok "FotoTakip durduruldu" || echo "  FotoTakip çalışmıyordu"
stop_matching "cloudflared tunnel --no-autoupdate" && ok "Tünel durduruldu" || echo "  Tünel çalışmıyordu"
sleep 1

# ---------- 2. yedek ----------
if [ "$NO_BACKUP" = 0 ] && [ -f "$DATA_DIR/fototakip.db" ]; then
  say "Yedek alınıyor (OpenAI anahtarı ve tünel token'ı yedeğe girmez)"
  bash "$APP_DIR/scripts/backup.sh" || die "Yedek alınamadı; hiçbir şey silinmedi. Yedeksiz silmek için: --yedeksiz"
  warn "Yedekte veritabanı var: hesaplar, parola özetleri ve müşteri bilgileri. Paylaşma; işin bitince silebilirsin."
fi

# ---------- 3. onay ----------
if [ "$ASSUME_YES" = 0 ]; then
  ( : > /dev/tty ) 2>/dev/null || die "Onay alınamıyor (terminal yok). Sorusuz çalıştırmak için: --evet"
  ask "Tüm FotoTakip verisi silinecek. Onaylamak için büyük harfle SIL yaz:" ""
  [ "$ANSWER" = "SIL" ] || die "Onay verilmedi; hiçbir şey silinmedi."
fi

# ---------- 4. veri ----------
if [ -d "$DATA_DIR" ]; then
  rm -rf -- "$DATA_DIR"
  ok "Veri klasörü silindi: veritabanı, fotoğraflar, imzalar, oturumlar, parolalar, gizli anahtarlar, kayıtlar"
fi

# ---------- 5. DNS ----------
if [ -n "${PREFIX:-}" ] && [[ "$PREFIX" == *com.termux* ]]; then
  R="$PREFIX/etc/resolv.conf"
  if [ -f "$R.fototakip-yedek" ]; then
    cp "$R.fototakip-yedek" "$R" && rm -f "$R.fototakip-yedek"
    ok "Termux DNS ayarı kurulum öncesine döndürüldü"
  elif grep -q '^# FotoTakip' "$R" 2>/dev/null; then
    warn "DNS FotoTakip tarafından değiştirilmiş ama eski ayarın yedeği yok; dokunulmadı ($R)."
  fi
fi

# ---------- 6. GitHub kimliği ----------
CRED="$HOME/.git-credentials"
if [ -f "$CRED" ] && grep -q 'github\.com' "$CRED"; then
  if [ -z "$GIT_CRED" ]; then
    if [ "$ASSUME_YES" = 1 ]; then GIT_CRED=0; else
      ask "Telefonda kayıtlı GitHub kimlik bilgisi (token) de silinsin mi? Sonraki yüklemede yeniden sorulur. [e/H]:" h
      case "$ANSWER" in e|E|evet|y|Y) GIT_CRED=1 ;; *) GIT_CRED=0 ;; esac
    fi
  fi
  if [ "$GIT_CRED" = 1 ]; then
    grep -v 'github\.com' "$CRED" > "$CRED.tmp" || true
    if [ -s "$CRED.tmp" ]; then mv "$CRED.tmp" "$CRED"; chmod 600 "$CRED"; else rm -f "$CRED.tmp" "$CRED"; fi
    ok "GitHub kimlik bilgisi silindi. Token'ı GitHub'da da iptal et: Settings › Developer settings › Personal access tokens"
  else
    echo "  GitHub kimlik bilgisi bırakıldı ($CRED)"
  fi
fi

echo
ok "Sıfırlama bitti. Kod klasörü ($APP_DIR) duruyor."
echo "Yeniden başlatmak için:  fototakip"
echo "İlk açılışta Termux ekranına bir kurulum kodu yazılır; tarayıcıda bu kodla yönetici hesabını aç."
