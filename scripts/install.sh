#!/usr/bin/env bash
# FotoTakip tek satırlık kurulum ve güncelleme (Termux). KULLANICI yerine deponun sahibini yaz:
#   curl -fsSL https://raw.githubusercontent.com/KULLANICI/fototakip/main/scripts/install.sh | bash -s -- --repo https://github.com/KULLANICI/fototakip.git
# Seçenekli:  ... | bash -s -- --repo URL --dns opendns --tunel
# Güncellemede --repo gerekmez; mevcut kurulumun kendi GitHub adresi kullanılır.
#
# Kod yoksa indirir, varsa günceller, sonra scripts/install-termux.sh'yi çalıştırır.
# Verilere (~/fototakip-data) dokunmaz.
set -euo pipefail

say()  { printf '\033[1;36m▸ %s\033[0m\n' "$*"; }
ok()   { printf '\033[1;32m✓ %s\033[0m\n' "$*"; }
die()  { printf '\033[1;31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

# "curl | bash" altında standart girdi bu betiğin kendisidir. Paket yöneticisi oradan okursa betiğin
# geri kalanını yutar; bu yüzden girdisi kapatılır ve ayar dosyası soruları varsayılanla geçilir.
pkg_quiet() {
  DEBIAN_FRONTEND=noninteractive pkg "$@" </dev/null
}

# Her şey bir fonksiyonun içinde: indirme yarıda kesilirse yarım betik çalışmaz.
main() {
  local REPO="${FOTOTAKIP_REPO:-}"
  local PASS=()
  while [ $# -gt 0 ]; do
    case "$1" in
      --repo) REPO="${2:-}"; shift; [ $# -gt 0 ] && shift ;;
      --repo=*) REPO="${1#--repo=}"; shift ;;
      *) PASS+=("$1"); shift ;;
    esac
  done
  local BRANCH="${FOTOTAKIP_BRANCH:-main}"
  local DIR="${FOTOTAKIP_DIR:-$HOME/fototakip}"

  if [ -n "${PREFIX:-}" ] && [[ "$PREFIX" == *com.termux* ]]; then
    say "Termux paketleri hazırlanıyor (git, python)"
    pkg_quiet update -y >/dev/null 2>&1 || true
    pkg_quiet install -y -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold git python \
      || die "git ve python kurulamadı. İnternet bağlantısını kontrol et; sonra 'pkg upgrade' çalıştırıp bu komutu tekrar dene."
  else
    command -v git >/dev/null || die "git gerekli."
    command -v python3 >/dev/null || die "python3 gerekli."
  fi

  if [ -d "$DIR/.git" ]; then
    say "FotoTakip güncelleniyor: $DIR"
    if ! git -C "$DIR" diff --quiet || ! git -C "$DIR" diff --cached --quiet; then
      die "$DIR içinde elle değiştirilmiş dosyalar var. Önce bunları kaydet veya geri al: git -C $DIR status"
    fi
    local BEFORE AFTER
    BEFORE="$(git -C "$DIR" rev-parse --short HEAD)"
    git -C "$DIR" fetch -q origin "$BRANCH" </dev/null || die "GitHub'a ulaşılamadı. İnternet bağlantısını kontrol et."
    if ! git -C "$DIR" merge -q --ff-only "origin/$BRANCH" 2>/dev/null; then
      # Depo yeniden kurulduysa (geçmiş değiştiyse) ileri sarma olmaz; kod klasörü GitHub'daki sürüme eşitlenir.
      # Kod klasöründe elle değişiklik olmadığı yukarıda doğrulandı; veriler ayrı klasörde, etkilenmez.
      # Telefondaki eski commit'ler kaybolmasın diye önce bir yedek dala alınır.
      local KEEP
      KEEP="yedek-$(date +%Y%m%d-%H%M%S)"
      git -C "$DIR" branch -f "$KEEP" HEAD
      say "Depo geçmişi değişmiş; kod GitHub'daki sürüme eşitleniyor (eski hâli '$KEEP' dalında duruyor)"
      git -C "$DIR" reset -q --hard "origin/$BRANCH" || die "Güncellenemedi. $DIR klasörünü silip komutu tekrar çalıştır."
    fi
    AFTER="$(git -C "$DIR" rev-parse --short HEAD)"
    if [ "$BEFORE" = "$AFTER" ]; then ok "Zaten güncel ($AFTER)"; else ok "Güncellendi: $BEFORE → $AFTER"; fi
  else
    [ -n "$REPO" ] || die "Depo adresi gerekli: ... | bash -s -- --repo https://github.com/KULLANICI/fototakip.git"
    if [ -e "$DIR" ]; then
      local OLD
      OLD="$DIR.eski-$(date +%Y%m%d-%H%M%S)"
      mv "$DIR" "$OLD"
      ok "Eski kurulum $OLD klasörüne taşındı (verilerin ~/fototakip-data içinde, etkilenmedi)"
    fi
    say "FotoTakip indiriliyor"
    GIT_TERMINAL_PROMPT=0 git clone -q --depth 20 -b "$BRANCH" "$REPO" "$DIR" </dev/null || die "İndirilemedi: $REPO"
    ok "İndirildi: $(git -C "$DIR" rev-parse --short HEAD)"
  fi

  # Sorular /dev/tty üzerinden sorulur; standart girdi (bu betik) alt betiğe verilmez.
  bash "$DIR/scripts/install-termux.sh" ${PASS[@]+"${PASS[@]}"} </dev/null

  if pgrep -f "python.* -m fototakip" >/dev/null 2>&1; then
    echo
    echo "FotoTakip şu an çalışıyor. Yeni sürüm için yeniden başlat:"
    echo "  pkill -f 'python.* -m fototakip'; fototakip"
  fi
}

main "$@"
