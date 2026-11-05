"""Komut satırı: python -m fototakip [--port 8080] [--data ~/fototakip-data] [--no-demo]"""

from __future__ import annotations

import argparse
import os
import signal
import socket
import sys
import threading

from . import __version__, db, images, seed
from .server import Config, make_server


def lan_addresses() -> list[str]:
    addrs = set()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        addrs.add(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    return sorted(a for a in addrs if not a.startswith("127."))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="fototakip", description="FotoTakip sunucusu")
    p.add_argument("--host", default=os.environ.get("FOTOTAKIP_HOST", "0.0.0.0"))
    p.add_argument("--port", type=int, default=int(os.environ.get("FOTOTAKIP_PORT", "8080")))
    p.add_argument("--data", default=os.environ.get("FOTOTAKIP_DATA", os.path.expanduser("~/fototakip-data")),
                   help="Veritabanı ve fotoğrafların klasörü")
    p.add_argument("--max-upload-mb", type=int, default=int(os.environ.get("FOTOTAKIP_MAX_UPLOAD_MB", "15")))
    p.add_argument("--no-demo", action="store_true", help="İlk açılışta örnek veri yükleme, yalnızca yönetici hesabı aç")
    p.add_argument("--quiet", action="store_true", help="İstek kayıtlarını yazma")
    p.add_argument("--geocoder", default=os.environ.get("FOTOTAKIP_GEOCODER", "on"),
                   help="Fotoğraf koordinatından adres bulma: on (OpenStreetMap), off ya da https://…/reverse")
    p.add_argument("--geocoder-contact", default=os.environ.get("FOTOTAKIP_GEOCODER_CONTACT", ""),
                   help="Nominatim'e gönderilen iletişim e-postası (isteğe bağlı)")
    p.add_argument("--version", action="version", version=f"FotoTakip {__version__}")
    args = p.parse_args(argv)

    cfg = Config(host=args.host, port=args.port, data_dir=os.path.abspath(os.path.expanduser(args.data)),
                 max_upload_mb=args.max_upload_mb, quiet=args.quiet,
                 geocoder=args.geocoder, geocoder_contact=args.geocoder_contact)
    try:
        server = make_server(cfg)
    except OSError as e:
        print(f"Sunucu başlatılamadı ({cfg.host}:{cfg.port}): {e}", file=sys.stderr)
        print("Port kullanımdaysa başka port dene: fototakip --port 8081", file=sys.stderr)
        return 1

    if db.is_empty(cfg.db_path):
        if args.no_demo:
            user, pw = seed.create_admin(cfg.db_path)
            print(f"\nYönetici hesabı oluşturuldu → kullanıcı: {user}  parola: {pw}  (girişten sonra değiştir)\n")
        else:
            seed.seed_demo(cfg.db_path, cfg.data_dir)
            print(f"\nÖrnek veri yüklendi. Hesaplar: yusuf (yönetici), mert, elif — parola: {seed.DEMO_PASSWORD}\n")

    print(f"FotoTakip {__version__} çalışıyor")
    print(f"  Bu telefonda:   http://localhost:{cfg.port}")
    for a in lan_addresses():
        print(f"  Aynı Wi-Fi'de:  http://{a}:{cfg.port}   (kamera/çevrimdışı için HTTPS tünel gerekir, README'ye bak)")
    print(f"  Veri klasörü:   {cfg.data_dir}")
    print(f"  Adres bulma:    {'açık (OpenStreetMap Nominatim)' if server.geo.enabled else 'kapalı'}")
    if not images.HAVE_PIL:
        print("  Uyarı: Pillow yok; fotoğraflar küçültülmeden saklanacak. Kur: pkg install python-pillow")
    print("Durdurmak için Ctrl+C\n", flush=True)

    def stop(*_):
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, stop)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.stopping.set()
        server.server_close()
        print("FotoTakip durdu.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
