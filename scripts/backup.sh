#!/usr/bin/env bash
# Veri klasörünü (veritabanı + fotoğraflar) tarihli bir zip'e yedekler.
# Kullanım: bash scripts/backup.sh [hedef_klasör]
# Termux'ta varsayılan hedef: telefonun İndirilenler klasörü (önce termux-setup-storage çalıştır).
set -euo pipefail
DATA_DIR="${FOTOTAKIP_DATA:-$HOME/fototakip-data}"
DEST="${1:-$HOME/storage/downloads}"
[ -d "$DEST" ] || DEST="$HOME"
[ -f "$DATA_DIR/fototakip.db" ] || { echo "Veri bulunamadı: $DATA_DIR" >&2; exit 1; }
STAMP="$(date '+%Y%m%d-%H%M')"
OUT="$DEST/fototakip-yedek-$STAMP.zip"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
python3 - "$DATA_DIR/fototakip.db" "$TMP/fototakip.db" <<'EOF'
import sqlite3, sys
src, dst = sqlite3.connect(sys.argv[1]), sqlite3.connect(sys.argv[2])
src.backup(dst); dst.close(); src.close()
EOF
python3 - "$OUT" "$TMP/fototakip.db" "$DATA_DIR" <<'EOF'
import os, sys, zipfile
out, db, data = sys.argv[1:4]
with zipfile.ZipFile(out, "w", zipfile.ZIP_STORED) as z:
    z.write(db, "fototakip.db")
    for sub in ("photos", "signatures"):
        base = os.path.join(data, sub)
        if os.path.isdir(base):
            for n in os.listdir(base):
                z.write(os.path.join(base, n), f"{sub}/{n}")
EOF
echo "Yedek hazır: $OUT ($(du -h "$OUT" | cut -f1))"
