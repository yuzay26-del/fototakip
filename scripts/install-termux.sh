#!/usr/bin/env bash
# FotoTakip Termux kurulumu. İnternetten kod indirmez; bu klasördeki kodu kurar.
# Kullanım:  bash scripts/install-termux.sh [--no-boot] [--dns opendns|cloudflare|google|quad9|dokunma] [--tunel] [--evet]
#   --dns     Termux içindeki programların kullanacağı DNS sunucusu (cloudflared için önemli)
#   --tunel   Dışarıdan erişim için cloudflared'i de kur (ücretsiz Cloudflare tüneli)
#   --evet    Soru sorma, varsayılanları kullan
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="${FOTOTAKIP_DATA:-$HOME/fototakip-data}"
PORT="${FOTOTAKIP_PORT:-8080}"
WITH_BOOT=1
DNS_CHOICE=""
WITH_TUNNEL=""
ASSUME_YES=0
while [ $# -gt 0 ]; do
  case "$1" in
    --no-boot) WITH_BOOT=0; shift ;;
    --dns) DNS_CHOICE="${2:-}"; shift 2 ;;
    --dns=*) DNS_CHOICE="${1#--dns=}"; shift ;;
    --tunel) WITH_TUNNEL=1; shift ;;
    --evet|-y) ASSUME_YES=1; shift ;;
    -h|--help) sed -n '2,6p' "$0"; exit 0 ;;
    *) echo "Bilinmeyen seçenek: $1" >&2; exit 2 ;;
  esac
done

# curl | bash ile çalışırken bile soruları klavyeden okuyabilmek için /dev/tty kullanılır
ask() {  # ask "soru" varsayılan -> cevap ANSWER değişkenine yazılır
  ANSWER="$2"
  # /dev/tty dosya olarak görünse bile terminal yoksa açılamaz (ör. Termux:Boot, otomasyon); gerçekten açmayı dene.
  if [ "$ASSUME_YES" = 0 ] && ( : > /dev/tty ) 2>/dev/null; then
    printf '%s ' "$1" > /dev/tty
    IFS= read -r ANSWER < /dev/tty || ANSWER="$2"
    [ -n "$ANSWER" ] || ANSWER="$2"
  fi
}

say()  { printf '\033[1;36m▸ %s\033[0m\n' "$*"; }
ok()   { printf '\033[1;32m✓ %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m! %s\033[0m\n' "$*"; }

# "curl | bash" ile çağrıldığında standart girdi kurulum betiğinin kendisidir; paket yöneticisi
# oradan okumasın diye girdisi kapatılır, ayar dosyası soruları varsayılanla geçilir.
pkg_quiet() {
  DEBIAN_FRONTEND=noninteractive pkg "$@" </dev/null
}
PKG_OPTS=(-y -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold)

IS_TERMUX=0
if [ -n "${PREFIX:-}" ] && [[ "$PREFIX" == *com.termux* ]]; then IS_TERMUX=1; fi
BIN_DIR="${PREFIX:-$HOME/.local}/bin"
[ "$IS_TERMUX" = 1 ] || { BIN_DIR="$HOME/.local/bin"; warn "Termux dışında çalışıyor; sistem paketleri kurulmayacak."; }

if [ ! -f "$APP_DIR/fototakip/__main__.py" ]; then
  echo "Hata: $APP_DIR içinde FotoTakip kodu yok. Betiği FotoTakip klasörünün içinden çalıştır." >&2
  exit 1
fi

if [ "$IS_TERMUX" = 1 ]; then
  say "Termux paketleri güncelleniyor"
  pkg_quiet update -y || warn "Paket listesi güncellenemedi; mevcut listeyle devam ediliyor."
  say "Python kuruluyor"
  pkg_quiet install "${PKG_OPTS[@]}" python || { echo "Hata: Python kurulamadı. İnternet bağlantısını kontrol et; 'pkg upgrade' çalıştırıp tekrar dene." >&2; exit 1; }
  say "Pillow kuruluyor (fotoğraf döndürme ve küçük resim için)"
  if pkg_quiet install "${PKG_OPTS[@]}" python-pillow; then ok "Pillow kuruldu"; else warn "Pillow kurulamadı; uygulama çalışır ama fotoğraflar küçültülmez."; fi
fi

PY="$(command -v python3 || command -v python || true)"
[ -n "$PY" ] || { echo "Hata: Python bulunamadı." >&2; exit 1; }
"$PY" - <<'EOF' || { echo "Hata: Python 3.10 veya üstü gerekiyor." >&2; exit 1; }
import sys
sys.exit(0 if sys.version_info >= (3, 10) else 1)
EOF
ok "Python: $("$PY" --version)"

# ---------- DNS ayarı ----------
if [ "$IS_TERMUX" = 1 ]; then
  RESOLV="$PREFIX/etc/resolv.conf"
  if [ -z "$DNS_CHOICE" ] && [ "$ASSUME_YES" = 1 ]; then
    DNS_CHOICE=dokunma
  fi
  if [ -z "$DNS_CHOICE" ]; then
    # resolv.conf yoksa ya da içinde nameserver satırı yoksa grep hata döner; kurulum bu yüzden durmamalı.
    CUR="$( (grep '^nameserver' "$RESOLV" 2>/dev/null || true) | awk '{print $2}' | head -2 | tr '\n' ' ')"
    echo
    echo "DNS sunucusu (Termux içindeki programlar için; cloudflared bazen sistem DNS'ini bulamaz):"
    echo "  1) OpenDNS      208.67.222.222, 208.67.220.220"
    echo "  2) Cloudflare   1.1.1.1, 1.0.0.1"
    echo "  3) Google       8.8.8.8, 8.8.4.4"
    echo "  4) Quad9        9.9.9.9, 149.112.112.112"
    echo "  5) Dokunma      (şu an: ${CUR:-sistem})"
    ask "Seçimin [1-5, varsayılan 5]:" 5
    case "$ANSWER" in 1) DNS_CHOICE=opendns ;; 2) DNS_CHOICE=cloudflare ;; 3) DNS_CHOICE=google ;; 4) DNS_CHOICE=quad9 ;; *) DNS_CHOICE=dokunma ;; esac
  fi
  case "$DNS_CHOICE" in
    opendns) NS="208.67.222.222 208.67.220.220" ;;
    cloudflare) NS="1.1.1.1 1.0.0.1" ;;
    google) NS="8.8.8.8 8.8.4.4" ;;
    quad9) NS="9.9.9.9 149.112.112.112" ;;
    dokunma|"") NS="" ;;
    *) warn "Bilinmeyen DNS seçimi: $DNS_CHOICE (dokunulmadı)"; NS="" ;;
  esac
  if [ -n "$NS" ]; then
    mkdir -p "$(dirname "$RESOLV")"
    if [ -f "$RESOLV" ] && [ ! -f "$RESOLV.fototakip-yedek" ]; then cp "$RESOLV" "$RESOLV.fototakip-yedek"; fi
    { echo "# FotoTakip: $DNS_CHOICE"; for ip in $NS; do echo "nameserver $ip"; done; } > "$RESOLV"
    ok "DNS: $DNS_CHOICE ($NS). Eski ayar: $RESOLV.fototakip-yedek"
  fi

  # ---------- tünel aracı ----------
  if [ -z "$WITH_TUNNEL" ]; then
    if command -v cloudflared >/dev/null 2>&1; then WITH_TUNNEL=1; else
      ask "Dışarıdan erişim için ücretsiz Cloudflare tüneli aracı (cloudflared) kurulsun mu? [e/H]:" h
      case "$ANSWER" in e|E|evet|y|Y) WITH_TUNNEL=1 ;; *) WITH_TUNNEL=0 ;; esac
    fi
  fi
  if [ "$WITH_TUNNEL" = 1 ] && ! command -v cloudflared >/dev/null 2>&1; then
    say "cloudflared kuruluyor"
    if pkg_quiet install "${PKG_OPTS[@]}" cloudflared; then ok "cloudflared kuruldu"; else warn "cloudflared kurulamadı; daha sonra 'pkg install cloudflared' ile kurabilirsin."; fi
  fi
fi

say "Komutlar oluşturuluyor: fototakip, fototakip-tunel, fototakip-dns"
mkdir -p "$BIN_DIR" "$DATA_DIR"
cat > "$BIN_DIR/fototakip" <<EOF
#!/usr/bin/env bash
cd "$APP_DIR" && exec "$PY" -m fototakip --data "\${FOTOTAKIP_DATA:-$DATA_DIR}" --port "\${FOTOTAKIP_PORT:-$PORT}" "\$@"
EOF
cat > "$BIN_DIR/fototakip-tunel" <<'EOF'
#!/usr/bin/env bash
# Diğer telefonlar için HTTPS adresi açar (kamera, konum ve çevrimdışı açılış HTTPS ister).
set -e
PORT="${FOTOTAKIP_PORT:-8080}"
if ! command -v cloudflared >/dev/null 2>&1; then
  echo "cloudflared kuruluyor..."
  pkg install -y cloudflared || { echo "cloudflared kurulamadı. README'deki 'HTTPS' bölümüne bak."; exit 1; }
fi
echo "Aşağıda https://….trycloudflare.com adresi çıkınca ekiple paylaş. Durdurmak: Ctrl+C"
exec cloudflared tunnel --no-autoupdate --url "http://127.0.0.1:$PORT"
EOF
cat > "$BIN_DIR/fototakip-dns" <<'DNS_EOF'
#!/usr/bin/env bash
# Termux DNS sunucusunu değiştirir:  fototakip-dns opendns|cloudflare|google|quad9|geri
set -e
R="$PREFIX/etc/resolv.conf"
case "${1:-}" in
  opendns) NS="208.67.222.222 208.67.220.220" ;;
  cloudflare) NS="1.1.1.1 1.0.0.1" ;;
  google) NS="8.8.8.8 8.8.4.4" ;;
  quad9) NS="9.9.9.9 149.112.112.112" ;;
  geri) if [ -f "$R.fototakip-yedek" ]; then cp "$R.fototakip-yedek" "$R"; echo "Eski DNS ayarı geri yüklendi."; exit 0; fi; echo "Yedek yok."; exit 1 ;;
  *) echo "Kullanım: fototakip-dns opendns|cloudflare|google|quad9|geri"; echo "Şu an:"; grep '^nameserver' "$R" 2>/dev/null || echo "  sistem varsayılanı"; exit 0 ;;
esac
if [ -f "$R" ] && [ ! -f "$R.fototakip-yedek" ]; then cp "$R" "$R.fototakip-yedek"; fi
{ echo "# FotoTakip: $1"; for ip in $NS; do echo "nameserver $ip"; done; } > "$R"
echo "DNS: $1 ($NS)"
DNS_EOF
chmod +x "$BIN_DIR/fototakip" "$BIN_DIR/fototakip-tunel" "$BIN_DIR/fototakip-dns"
ok "Komutlar hazır: $BIN_DIR"

if [ "$IS_TERMUX" = 1 ] && [ "$WITH_BOOT" = 1 ]; then
  mkdir -p "$HOME/.termux/boot"
  cat > "$HOME/.termux/boot/fototakip.sh" <<EOF
#!/data/data/com.termux/files/usr/bin/sh
termux-wake-lock
nohup "$BIN_DIR/fototakip" --quiet >> "$DATA_DIR/sunucu.log" 2>&1 &
EOF
  chmod +x "$HOME/.termux/boot/fototakip.sh"
  ok "Telefon açılınca otomatik başlatma hazır (Termux:Boot uygulaması kurulu olmalı)"
fi

say "Kurulum testi"
"$PY" - "$APP_DIR" <<'EOF'
import sys
sys.path.insert(0, sys.argv[1])
import fototakip.server, fototakip.images as im
print("  sunucu modülü yüklendi; Pillow:", "var" if im.HAVE_PIL else "yok")
EOF

echo
ok "FotoTakip kuruldu."
cat <<EOF

  Başlat:          fototakip
  Bu telefonda:    http://localhost:$PORT
  Dışarıdan erişim:  uygulamada Yönetim > Sistem > Dışarıdan erişim
  DNS değiştirmek:   fototakip-dns opendns
  Veriler:         $DATA_DIR

  Önemli: Android Ayarlar > Uygulamalar > Termux > Pil > "Kısıtlamasız" seç,
  yoksa ekran kapanınca sunucu durabilir.
EOF
