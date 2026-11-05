#!/usr/bin/env bash
# FotoTakip'i GitHub'a yükler. Yüklemeden önce ve sonra kontrol eder:
#   1. Depo GitHub'da var mı, erişim var mı?
#   2. Bu sürüm zaten yüklü mü? (yerel commit == GitHub'daki commit)
#   3. GitHub'da burada olmayan commit var mı? (varsa zorla yazmaz, durur)
#   4. Yüklemeden sonra GitHub'daki commit yerel commit ile aynı mı?
#
# Kullanım:  bash scripts/github-upload.sh [-r https://github.com/KULLANICI/DEPO.git] [-b main] [-m "commit mesajı"] [--check]
#   --check   Hiçbir şey yüklemeden yalnızca durumu raporlar.
#   --adopt   GitHub'daki geçmişin üzerine ekle (ör. GitHub'da depo README ile açıldıysa).
set -euo pipefail

REMOTE_URL="${FOTOTAKIP_REMOTE:-https://github.com/yuzay26-del/fototakip.git}"
BRANCH="main"
MESSAGE=""
CHECK_ONLY=0
ADOPT=0
INIT_NOW=0
while [ $# -gt 0 ]; do
  case "$1" in
    -r) REMOTE_URL="$2"; shift 2 ;;
    -b) BRANCH="$2"; shift 2 ;;
    -m) MESSAGE="$2"; shift 2 ;;
    --check) CHECK_ONLY=1; shift ;;
    --adopt) ADOPT=1; shift ;;
    -h|--help) sed -n '2,10p' "$0"; exit 0 ;;
    *) echo "Bilinmeyen seçenek: $1" >&2; exit 2 ;;
  esac
done

say()  { printf '\033[1;36m▸ %s\033[0m\n' "$*"; }
ok()   { printf '\033[1;32m✓ %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m! %s\033[0m\n' "$*"; }
die()  { printf '\033[1;31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

command -v git >/dev/null || die "git yok. Termux'ta: pkg install git"
cd "$(dirname "${BASH_SOURCE[0]}")/.."
[ -f fototakip/__main__.py ] || die "Bu betik FotoTakip klasöründe çalışmalı."

# --- yerel depo ---
if [ ! -d .git ]; then
  [ "$CHECK_ONLY" = 1 ] && { warn "Bu klasör henüz git deposu değil; hiç yüklenmemiş."; exit 3; }
  say "Yerel git deposu oluşturuluyor"
  git init -q -b "$BRANCH"
  INIT_NOW=1
fi
git config user.name >/dev/null || git config user.name "FotoTakip"
git config user.email >/dev/null || git config user.email "fototakip@localhost"

DIRTY=0
if [ -n "$(git status --porcelain)" ]; then
  if [ "$CHECK_ONLY" = 1 ]; then
    DIRTY=1
    warn "Commit edilmemiş değişiklikler var:"; git status --short | head -20
  else
    say "Değişiklikler commit ediliyor"
    git add -A
    git commit -q -m "${MESSAGE:-FotoTakip güncellemesi $(date '+%Y-%m-%d %H:%M')}"
  fi
fi
git rev-parse --verify -q HEAD >/dev/null || die "Commit edilecek dosya yok."
LOCAL_SHA="$(git rev-parse HEAD)"
ok "Yerel sürüm: ${LOCAL_SHA:0:7} · $(git log -1 --format=%s)"

# --- 1. depo var mı ---
say "GitHub deposu kontrol ediliyor: $REMOTE_URL"
if ! LS="$(GIT_TERMINAL_PROMPT=0 git ls-remote "$REMOTE_URL" 2>&1)"; then
  echo "$LS" | tail -3 >&2
  cat >&2 <<EOF

Depoya ulaşılamadı. Olası nedenler:
  • Depo yok → https://github.com/new adresinde boş bir depo oluştur (README ekleme).
  • Özel depoya giriş yapılmamış → GitHub kişisel erişim anahtarı (token) gerekir:
      git config --global credential.helper store
      sonra bu betiği tekrar çalıştır; kullanıcı adı ve token sorulur.
EOF
  exit 4
fi
REMOTE_SHA="$(echo "$LS" | awk -v ref="refs/heads/$BRANCH" '$2==ref {print $1}')"

# --- 2. zaten yüklü mü ---
if [ -z "$REMOTE_SHA" ]; then
  if [ -n "$LS" ]; then warn "Depo var ama '$BRANCH' dalı yok."; else ok "Depo var ve boş."; fi
  STATE="empty"
elif [ "$REMOTE_SHA" = "$LOCAL_SHA" ] && [ "$DIRTY" = 1 ]; then
  warn "Son commit GitHub'da (${LOCAL_SHA:0:7}), ama yukarıdaki değişiklikler henüz yüklenmedi. Yüklemek için --check olmadan çalıştır."
  exit 5
elif [ "$REMOTE_SHA" = "$LOCAL_SHA" ]; then
  ok "Zaten yüklü: GitHub'daki '$BRANCH' bu sürümle aynı (${LOCAL_SHA:0:7}). Yapılacak bir şey yok."
  exit 0
else
  git fetch -q "$REMOTE_URL" "$BRANCH" || die "GitHub'dan çekilemedi."
  if git merge-base --is-ancestor "$REMOTE_SHA" "$LOCAL_SHA"; then
    AHEAD="$(git rev-list --count "$REMOTE_SHA..$LOCAL_SHA")"
    ok "GitHub'daki sürüm (${REMOTE_SHA:0:7}) eski; $AHEAD yeni commit yüklenecek."
    STATE="behind"
  elif git merge-base --is-ancestor "$LOCAL_SHA" "$REMOTE_SHA"; then
    die "GitHub'daki sürüm buradakinden yeni. Önce çek: git pull $REMOTE_URL $BRANCH"
  elif [ "$INIT_NOW" = 1 ] || [ "$ADOPT" = 1 ]; then
    # Yerel depo yeni açıldı (ya da --adopt): GitHub'daki geçmişi koru, bu klasörü onun üzerine yeni commit yap.
    [ "$CHECK_ONLY" = 1 ] && { warn "GitHub'da başka commit'ler var; yüklerken onların üzerine eklenecek."; exit 5; }
    say "GitHub'daki geçmiş korunuyor; bu sürüm onun üzerine ekleniyor"
    git reset -q --soft "$REMOTE_SHA"
    git add -A
    git commit -q -m "${MESSAGE:-FotoTakip güncellemesi $(date '+%Y-%m-%d %H:%M')}"
    LOCAL_SHA="$(git rev-parse HEAD)"
    ok "Yeni sürüm: ${LOCAL_SHA:0:7} (üstünde ${REMOTE_SHA:0:7})"
    STATE="behind"
  else
    # --- 3. ayrışmış geçmiş ---
    die "GitHub'da burada olmayan commit'ler var (ayrışmış geçmiş). Üzerine yazılmadı. GitHub'daki geçmişi koruyup üstüne eklemek için: --adopt"
  fi
fi

if [ "$CHECK_ONLY" = 1 ]; then
  warn "Yükleme gerekli (durum: $STATE). Yüklemek için --check olmadan çalıştır."
  exit 5
fi

say "Yükleniyor"
git push "$REMOTE_URL" "HEAD:refs/heads/$BRANCH"

# --- 4. doğrulama ---
say "Yükleme doğrulanıyor"
AFTER="$(git ls-remote "$REMOTE_URL" "refs/heads/$BRANCH" | awk '{print $1}')"
[ "$AFTER" = "$LOCAL_SHA" ] || die "Doğrulama başarısız: GitHub'da ${AFTER:0:7}, yerelde ${LOCAL_SHA:0:7}."
git remote get-url origin >/dev/null 2>&1 || git remote add origin "$REMOTE_URL"
ok "Yüklendi ve doğrulandı: ${LOCAL_SHA:0:7} → $REMOTE_URL ($BRANCH)"
