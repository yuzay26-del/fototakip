#!/usr/bin/env bash
# install.sh'yi Termux Docker imajında baştan sona dener ve /health'i doğrular.
# Kullanım: bash scripts/test-termux-install.sh   (Docker gerekir, x86_64)
set -euo pipefail

IMAGE="${TERMUX_IMAGE:-termux/termux-docker:x86_64}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

docker pull "$IMAGE"

# Repo salt okunur bağlanır; konteyner içinde kopyalanır (sahiplik sorunlarını önler).
docker run --rm \
  -v "$ROOT:/repo:ro" \
  -e FOTOTAKIP_SKIP_WEB=1 \
  "$IMAGE" bash -c '
    set -euo pipefail
    cp -r /repo "$HOME/fototakip"
    cd "$HOME/fototakip"
    rm -rf backend/.venv backend/.env backend/data
    bash scripts/install.sh

    fototakip > "$HOME/server.log" 2>&1 &
    for _ in $(seq 1 60); do
      if body="$(curl -fsS http://127.0.0.1:8080/health 2>/dev/null)"; then
        echo "health: $body"
        case "$body" in
          *"\"mode\":\"termux\""*) echo "BAŞARILI"; exit 0 ;;
          *) echo "Beklenmeyen mod"; exit 1 ;;
        esac
      fi
      sleep 1
    done
    echo "Sunucu 60 sn içinde açılmadı"; cat "$HOME/server.log"; exit 1
  '
