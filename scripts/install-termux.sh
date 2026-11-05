#!/usr/bin/env bash
# FotoTakip Termux kurulumu. İnternetten kod indirmez; bu klasördeki kodu kurar.
# Kullanım:  bash scripts/install-termux.sh [--no-boot]
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="${FOTOTAKIP_DATA:-$HOME/fototakip-data}"
PORT="${FOTOTAKIP_PORT:-8080}"
WITH_BOOT=1
for arg in "$@"; do
  case "$arg" in
    --no-boot) WITH_BOOT=0 ;;
    -h|--help) sed -n '2,4p' "$0"; exit 0 ;;
    *) echo "Bilinmeyen seçenek: $arg" >&2; exit 2 ;;
  esac
done

say()  { printf '\033[1;36m▸ %s\033[0m\n' "$*"; }
ok()   { printf '\033[1;32m✓ %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m! %s\033[0m\n' "$*"; }

IS_TERMUX=0
if [ -n "${PREFIX:-}" ] && [[ "$PREFIX" == *com.termux* ]]; then IS_TERMUX=1; fi
BIN_DIR="${PREFIX:-$HOME/.local}/bin"
[ "$IS_TERMUX" = 1 ] || { BIN_DIR="$HOME/.local/bin"; warn "Termux dışında çalışıyor; sistem paketleri kurulmayacak."; }

if [ ! -f "$APP_DIR/fototakip/__main__.py" ]; then
  echo "Hata: $APP_DIR içinde FotoTakip kodu yok. Zip'i açtığın klasörde çalıştır." >&2
  exit 1
fi

if [ "$IS_TERMUX" = 1 ]; then
  say "Termux paketleri güncelleniyor"
  pkg update -y
  say "Python kuruluyor"
  pkg install -y python
  say "Pillow kuruluyor (fotoğraf döndürme ve küçük resim için)"
  if pkg install -y python-pillow; then ok "Pillow kuruldu"; else warn "Pillow kurulamadı; uygulama çalışır ama fotoğraflar küçültülmez."; fi
fi

PY="$(command -v python3 || command -v python || true)"
[ -n "$PY" ] || { echo "Hata: Python bulunamadı." >&2; exit 1; }
"$PY" - <<'EOF' || { echo "Hata: Python 3.10 veya üstü gerekiyor." >&2; exit 1; }
import sys
sys.exit(0 if sys.version_info >= (3, 10) else 1)
EOF
ok "Python: $("$PY" --version)"

say "Komutlar oluşturuluyor: fototakip, fototakip-tunel"
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
exec cloudflared tunnel --url "http://localhost:$PORT"
EOF
chmod +x "$BIN_DIR/fototakip" "$BIN_DIR/fototakip-tunel"
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
  Diğer telefonlar için HTTPS:  yeni Termux oturumunda  fototakip-tunel
  Veriler:         $DATA_DIR

  Önemli: Android Ayarlar > Uygulamalar > Termux > Pil > "Kısıtlamasız" seç,
  yoksa ekran kapanınca sunucu durabilir.
EOF
