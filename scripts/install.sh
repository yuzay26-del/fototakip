#!/usr/bin/env bash
# FotoTakip tek satırlık kurulum ve güncelleme (Termux):
#   curl -fsSL https://raw.githubusercontent.com/yuzay26-del/fototakip/main/scripts/install.sh | bash
#
# Kod yoksa indirir, varsa günceller, sonra scripts/install-termux.sh'yi çalıştırır.
# Verilere (~/fototakip-data) dokunmaz.
set -euo pipefail

REPO="${FOTOTAKIP_REPO:-https://github.com/yuzay26-del/fototakip.git}"
BRANCH="${FOTOTAKIP_BRANCH:-main}"
DIR="${FOTOTAKIP_DIR:-$HOME/fototakip}"

say()  { printf '\033[1;36m▸ %s\033[0m\n' "$*"; }
ok()   { printf '\033[1;32m✓ %s\033[0m\n' "$*"; }
die()  { printf '\033[1;31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

if [ -n "${PREFIX:-}" ] && [[ "$PREFIX" == *com.termux* ]]; then
  say "Termux paketleri hazırlanıyor (git, python)"
  pkg update -y >/dev/null || true
  pkg install -y git python
else
  command -v git >/dev/null || die "git gerekli."
  command -v python3 >/dev/null || die "python3 gerekli."
fi

if [ -d "$DIR/.git" ]; then
  say "FotoTakip güncelleniyor: $DIR"
  if ! git -C "$DIR" diff --quiet || ! git -C "$DIR" diff --cached --quiet; then
    die "$DIR içinde elle değiştirilmiş dosyalar var. Önce bunları kaydet veya geri al: git -C $DIR status"
  fi
  BEFORE="$(git -C "$DIR" rev-parse --short HEAD)"
  git -C "$DIR" fetch -q origin "$BRANCH"
  git -C "$DIR" merge -q --ff-only "origin/$BRANCH" || die "Güncelleme birleştirilemedi. $DIR klasörünü silip komutu tekrar çalıştır."
  AFTER="$(git -C "$DIR" rev-parse --short HEAD)"
  [ "$BEFORE" = "$AFTER" ] && ok "Zaten güncel ($AFTER)" || ok "Güncellendi: $BEFORE → $AFTER"
else
  if [ -e "$DIR" ]; then
    OLD="$DIR.eski-$(date +%Y%m%d-%H%M)"
    mv "$DIR" "$OLD"
    ok "Eski kurulum $OLD klasörüne taşındı (verilerin ~/fototakip-data içinde, etkilenmedi)"
  fi
  say "FotoTakip indiriliyor"
  git clone -q --depth 20 -b "$BRANCH" "$REPO" "$DIR" || die "İndirilemedi: $REPO"
  ok "İndirildi: $(git -C "$DIR" rev-parse --short HEAD)"
fi

bash "$DIR/scripts/install-termux.sh" "$@"

if pgrep -f "python.* -m fototakip" >/dev/null 2>&1; then
  echo
  echo "FotoTakip şu an çalışıyor. Yeni sürüm için yeniden başlat:"
  echo "  pkill -f 'python.* -m fototakip'; fototakip"
fi
